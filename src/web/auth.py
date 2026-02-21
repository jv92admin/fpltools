"""Supabase auth helpers for the web app."""

from supabase import create_client
from alfred_fpl.config import settings


def get_supabase_client():
    return create_client(settings.supabase_url, settings.supabase_key)


def sign_in(email: str, password: str) -> dict | None:
    """Sign in with email/password. Returns {user_id, email} or None."""
    client = get_supabase_client()
    try:
        res = client.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
        if res.user:
            return {"user_id": res.user.id, "email": res.user.email}
    except Exception:
        pass
    return None


def sign_up(email: str, password: str) -> dict | None:
    """Sign up with email/password. Returns {user_id, email} or None."""
    client = get_supabase_client()
    try:
        res = client.auth.sign_up({"email": email, "password": password})
        if res.user and res.session:
            return {"user_id": res.user.id, "email": res.user.email}
    except Exception:
        pass
    return None
