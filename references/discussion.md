Understood. Taken together, these two docs actually form a coherent product if you treat them as two distinct “modes” with a shared plan object:

Plan Mode (companion analytics + planning UI)

Apply Mode (WebView execution browser + guided stepper overlay)

Below is the tightest way to unify them, identify the key decisions you need to make now, and lay out an MVP that is realistic, mobile-first, and consistent with your “no auth ownership / no automation / no scraping” posture.

1) The unifying product definition
What you are building

A mobile companion that helps a user:

Plan: understand squad, league context, and decide a set of actions (ExecutionPlan).

Apply: execute those actions inside the official FPL site with a guided overlay.

The core wedge

Your wedge is not “better predictions.” It is:

significantly better execution UX on mobile, plus

a tight loop: plan → apply → replan → resume apply, without the checklist friction.

That is meaningfully differentiated, and it stays aligned with your constraints.

2) What you should decide now (because it affects architecture)

These are the decisions that will determine whether you can ship quickly without rework.

A) “Data posture”: client-only vs thin backend

Given your goals, the cleanest path is:

Client-first data for most read-only views (fetch public endpoints directly or via a minimal proxy).

A thin backend only if required for:

push notifications,

caching (rate-limits and performance),

friend-group aggregation (mini-league ownership/differentials),

optional telemetry.

If you do not need push in MVP, you can delay the backend.

Recommendation: ship MVP with minimal backend (optional proxy + analytics). Add push + aggregation later.

B) Account model: none vs “light identity”

You can avoid FPL OAuth and still have an app identity:

App-level identity (anonymous/Apple/Google sign-in) is separate from FPL.

This allows persistence across devices, friend-groups, and sharing plans.

Recommendation: implement app identity early (even anonymous with upgrade path). It’s hard to retrofit friend-group later without it.

C) Apply Mode session handling

Your Apply Mode depends on WebView cookies/session persistence.

Key choice:

Single persistent WebView instance (best for “pause/replan/resume”).

Or recreate WebView per entry (simpler, but breaks the loop).

Recommendation: persistent WebView instance + background it when replanning.

D) Plan format: “execution-first” schema

Your ExecutionPlan object should be the canonical artifact across both docs.

Make it:

deterministic,

step-ordered,

and diffable.

You already have this; the key is adding:

plan versioning,

step mapping rules,

and a stable player identity mapping.

3) MVP scope that actually ships

Your “MVP Cut” is good. I’d tighten it further into a sequence that guarantees value quickly.

MVP v0 (2–3 core screens)

Plan Summary Screen

show plan summary (FTs, hit, bank, chip intent)

show “steps preview” list

CTA: Apply on FPL

Apply Mode

WebView (Transfers or Pick Team)

bottom-sheet stepper overlay

Mark Done / Back / Reset / Replan / Exit

Completed state

Replan (minimal)

for MVP, replanning can be as simple as editing the plan steps in-app, even manually, as long as the loop works.

Keep out of MVP: live scoring, league insights, push notifications, “ownership/differential analysis.” Those become Phase 2 once the execution wedge is proven.

Why: if Apply Mode isn’t sticky, the rest won’t matter.

4) Phase 2 roadmap: bring in the companion features without exploding scope

Once Apply Mode is stable, layer in the “fun / usability” features as read-only modules that feed better plans.

A sane order:

Phase 2A: “Planner that produces ExecutionPlans”

Multi-week planner (lightweight)

Transfer comparison view

Injury/flags tracker (basic: status + news)

Fixture difficulty view (non-predictive, just context)

Phase 2B: “Rivalry + mini-league”

League standings snapshot

Rival compare cards (your XI vs theirs, captain diffs)

League transfer round-up (simple counts + highlights)

Phase 2C: “Live experience”

Live GW tracker

“Players remaining” and captaincy swing view

Optional: push alerts (only if you add backend / background fetch)

This ordering keeps each phase valuable and minimizes rebuild.

5) Implementation notes: what will bite you if you don’t plan for it
A) WebView hardening checklist (mobile reality)

Handle:

deep links and redirects,

“open in external browser” suppression (or controlled allow-list),

session expiration gracefully (“You’ve been logged out; continue in WebView”).

Set “sensitive screen” flags where possible (Android secure flag; iOS equivalent patterns).

Ensure overlay gestures do not interfere with the underlying page (hit-testing).

B) Step correctness without DOM parsing

Because you can’t validate state, your UX must compensate:

Each step should include a “how to” micro-instruction (“On the Transfers page, tap X, then…”).

Have a “Show me where” helper that navigates by URL only (not DOM), e.g. “Go to Transfers,” “Go to Pick Team.”

Make “Mark Done” feel safe:

“Mark Done” + “Undo” (snackbar)

“I’m stuck” → opens a help drawer with troubleshooting tips.

C) Plan diffs and resume rules

You mentioned: restart recommended if transfers changed. Make that deterministic:

Diff categories:

Transfers changed (restart)

Captain/vice changed (remap)

Bench order changed (remap)

Chip intent changed (restart or soft reset depending on chip)

You want the user to feel “the app knows what changed” even though you’re not reading the page.

D) Rate limits and caching (even in a “grey area” posture)

Even if you stay read-only:

cache bootstrap-static for long TTL (hours),

cache fixtures moderately,

never let each client poll live endpoints aggressively from the device.

If/when you add friend-group ownership aggregation, you will need either:

a backend aggregator, or

strict per-user on-demand computation with tight caps.

6) What I would change in your docs (small but high leverage)
Clarify “player squad” language

Use “manager’s squad/picks” vs “player’s squad,” to avoid confusion in future implementation and UX copy.

Add an explicit “Operating Mode” section

Define:

Apply Mode (WebView + overlay; no auth ownership)

Data Mode (public endpoints for read-only context)
This prevents the roadmap from accidentally drifting into “we need to log into FPL to read stuff.”

Add a “Not in MVP” list to the feature scope doc

Your second doc is broad; tag features as:

MVP (must)

V1 (next)

V2 (later)
Otherwise it will balloon.