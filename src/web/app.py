"""FastAPI web app for Alfred FPL chat UI."""

import asyncio
import glob
import os
import sys
import tempfile
import time
from pathlib import Path

import markdown
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeSerializer

# Add src to path for alfred imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import alfred_fpl  # noqa: F401 — triggers domain registration

from alfred.graph.workflow import run_alfred

from web.auth import sign_in, sign_up
from web.sessions import create_session, delete_session, get_session, cleanup_expired

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Alfred FPL")

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Cookie signing key — fine for local dev, replace for production
SECRET_KEY = os.environ.get("WEB_SECRET_KEY", "alfred-fpl-dev-secret")
signer = URLSafeSerializer(SECRET_KEY)
COOKIE_NAME = "alfred_session"

MD_EXTENSIONS = ["tables", "fenced_code", "nl2br"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_session_from_request(request: Request):
    """Extract session from signed cookie."""
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        return None
    try:
        session_id = signer.loads(cookie)
    except Exception:
        return None
    return get_session(session_id)


def _set_session_cookie(response, session_id: str):
    """Set signed session cookie on response."""
    signed = signer.dumps(session_id)
    response.set_cookie(
        COOKIE_NAME, signed, httponly=True, samesite="lax", max_age=7200,
    )
    return response


def _md_to_html(text: str) -> str:
    """Convert markdown response to HTML."""
    return markdown.markdown(text, extensions=MD_EXTENSIONS)


def _find_new_charts(since_ts: float) -> list[str]:
    """Find chart PNGs generated since timestamp."""
    chart_dir = tempfile.gettempdir()
    patterns = [
        os.path.join(chart_dir, "fpl_exec_*", "*.png"),
        os.path.join(chart_dir, "fpl_charts_*", "*.png"),
    ]
    paths = []
    for pattern in patterns:
        for p in glob.glob(pattern):
            if os.path.getmtime(p) >= since_ts:
                paths.append(p)
    return paths


def _chart_path_to_url(filepath: str) -> str:
    """Convert absolute chart path to a servable URL."""
    # Serve as /charts/dirname/filename.png
    parts = Path(filepath).parts
    # Take the last two parts: temp_dir_name/file.png
    return f"/charts/{parts[-2]}/{parts[-1]}"


# ---------------------------------------------------------------------------
# Routes: Auth
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    session = _get_session_from_request(request)
    if session:
        return RedirectResponse("/chat", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/auth/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    user = sign_in(email, password)
    if not user:
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Invalid email or password."}
        )
    session = create_session(user["user_id"])
    response = RedirectResponse("/chat", status_code=302)
    _set_session_cookie(response, session.session_id)
    return response


@app.post("/auth/signup")
async def signup(request: Request, email: str = Form(...), password: str = Form(...)):
    user = sign_up(email, password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Sign-up failed. Email may already be registered."},
        )
    session = create_session(user["user_id"])
    response = RedirectResponse("/chat", status_code=302)
    _set_session_cookie(response, session.session_id)
    return response


@app.post("/auth/logout")
async def logout():
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response


# ---------------------------------------------------------------------------
# Routes: Chat
# ---------------------------------------------------------------------------

@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    session = _get_session_from_request(request)
    if not session:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "messages": session.messages,
    })


@app.post("/chat/send")
async def chat_send(request: Request, message: str = Form(...)):
    """Handle a chat message. Returns SSE stream with progress + final response."""
    session = _get_session_from_request(request)
    if not session:
        return RedirectResponse("/", status_code=302)

    async def event_stream():
        # Record user message
        session.messages.append({"role": "user", "content": message})

        # Start alfred in background
        start_ts = time.time()
        task = asyncio.create_task(_run_alfred_task(session, message))

        # Send progress events while waiting
        stages = [
            (0, "Understanding your question..."),
            (3, "Planning approach..."),
            (7, "Fetching data..."),
            (15, "Analyzing..."),
            (30, "Still working..."),
            (60, "Complex analysis in progress..."),
        ]
        stage_idx = 0

        while not task.done():
            elapsed = time.time() - start_ts
            if stage_idx < len(stages) and elapsed >= stages[stage_idx][0]:
                stage_text = stages[stage_idx][1]
                yield f"event: progress\ndata: {stage_text}\n\n"
                stage_idx += 1
            await asyncio.sleep(0.5)

        # Get result
        response_html, chart_urls, error = task.result()

        if error:
            yield f"event: error\ndata: {error}\n\n"
        else:
            # Send chart URLs if any
            for url in chart_urls:
                yield f"event: chart\ndata: {url}\n\n"

            # Send final response (replace newlines for SSE data field)
            html_oneline = response_html.replace("\n", "&#10;")
            yield f"event: message\ndata: {html_oneline}\n\n"

        yield "event: done\ndata: \n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def _run_alfred_task(session, message: str) -> tuple[str, list[str], str | None]:
    """Run alfred and return (response_html, chart_urls, error_or_none)."""
    chart_check_ts = time.time()
    try:
        response, session.conversation = await run_alfred(
            user_message=message,
            user_id=session.user_id,
            conversation=session.conversation,
        )

        # Convert markdown to HTML
        response_html = _md_to_html(response)

        # Find charts generated during this call
        chart_paths = _find_new_charts(chart_check_ts)
        chart_urls = [_chart_path_to_url(p) for p in chart_paths]

        # Inject chart images into response HTML
        if chart_urls:
            chart_html = "".join(
                f'<img src="{url}" class="chart-img" alt="Chart" />'
                for url in chart_urls
            )
            response_html += chart_html

        # Store in session history
        session.messages.append({
            "role": "assistant",
            "content": response_html,
            "charts": chart_urls,
        })

        return response_html, chart_urls, None

    except Exception as e:
        error_msg = f"Something went wrong: {e}"
        session.messages.append({"role": "assistant", "content": error_msg, "error": True})
        return "", [], error_msg


# ---------------------------------------------------------------------------
# Routes: Charts
# ---------------------------------------------------------------------------

@app.get("/charts/{dirname}/{filename}")
async def serve_chart(dirname: str, filename: str):
    """Serve a chart PNG from the temp directory."""
    filepath = Path(tempfile.gettempdir()) / dirname / filename
    if not filepath.exists() or not filepath.suffix == ".png":
        return HTMLResponse("Not found", status_code=404)
    return StreamingResponse(
        open(filepath, "rb"),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


# ---------------------------------------------------------------------------
# Routes: Conversation management
# ---------------------------------------------------------------------------

@app.post("/chat/reset")
async def chat_reset(request: Request):
    """Reset the conversation (start fresh)."""
    session = _get_session_from_request(request)
    if session:
        session.reset_conversation()
    return RedirectResponse("/chat", status_code=302)


# ---------------------------------------------------------------------------
# Startup / cleanup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    """Periodic session cleanup."""
    async def _cleanup_loop():
        while True:
            await asyncio.sleep(300)  # every 5 minutes
            cleanup_expired()
    asyncio.create_task(_cleanup_loop())
