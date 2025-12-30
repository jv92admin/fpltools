Feature Doc: Guided Apply Mode (Native Wrapper App)
Summary

Build a lightweight native mobile app that functions as a dedicated “FPL execution browser” with an overlay-guided stepper. Users authenticate and complete all actions directly on the official FPL site inside an in-app browser (WebView). Our app never handles credentials, never scrapes, never confirms actions via endpoints, and never automates clicks. It simply provides a structured, intuitive walkthrough for applying a previously finalized plan (transfers, captain/bench, chip intent) and enables seamless switching back to replanning.

Goals and Non-Goals
Goals

Provide a markedly better “apply the plan” experience than a static checklist.

Work reliably on mobile (primary requirement).

Maintain a strict posture of no auth ownership and no automation.

Support “pause, replan, resume” without losing user progress.

Non-Goals

No OAuth, no credential handling, no session storage.

No scraping/DOM parsing, no network interception, no endpoint confirmations.

No “one-click transfers” or unattended execution.

No guarantees that the user completed steps correctly (trust-based UX).

User Experience
Entry Points

In the main planning app: “Apply on FPL” CTA once a plan is finalized.

“Resume apply” CTA when an in-progress execution exists.

Primary Flow

User taps Apply on FPL

App opens an in-app WebView directly to the relevant FPL surface:

Transfers page if transfers exist

Pick Team page if only lineup/captain/bench changes

A persistent overlay (bottom sheet) shows:

Plan summary (GW, FT impact, hit, bank)

Step-by-step checklist (one action per step)

Controls: Mark Done, Back, Replan, Exit

User completes actions in the WebView and marks steps done in the overlay.

On final step, overlay shows “Completed” state + exit options.

Key UX Capability: Replan and Resume

Overlay includes Replan at all times.

Replan takes the user back to the planning UI (within the app) while preserving:

WebView session state (FPL still open in background)

Step progress state

Returning to Apply Mode resumes at the last incomplete step.

If the user changes the plan: prompt with Restart steps vs Continue (default restart if transfers changed).

Functional Requirements
A) WebView “FPL Browser”

Open arbitrary FPL URLs (Transfers / Pick Team / My Team, etc.).

Preserve the user’s logged-in session within the WebView using standard WebView cookie storage.

Explicit privacy posture:

Do not read cookies

Do not inject scripts

Do not collect page content

B) Guided Stepper Overlay

Render steps derived from a finalized ExecutionPlan object.

Step types:

Transfer out (player A)

Transfer in (player B)

Confirm transfers

Set captain/vice

Set bench order

Activate chip (intent-only; user executes)

Each step includes:

Action instruction (short, imperative)

Player card(s): name, club, position, price at planning time

“Mark Done” button

Progress UI:

Step count (e.g., 3/7)

Collapsible plan summary

“Reset progress” option

C) State & Persistence

Persist execution progress per plan:

plan_id

completed step IDs

timestamps

Resume rules:

If same plan: resume

If updated plan:

if transfers changed → restart recommended

if only captain/bench changed → allow continue with step map

D) Safety / Guardrails

Prominent disclaimers in Apply Mode:

“This is a guided walkthrough. You complete and confirm changes on FPL.”

No logging of WebView URLs beyond basic diagnostics (optional and privacy-reviewed).

No screen recording by default; sensitive-screen flags enabled where appropriate.

Data Model (Minimal)
ExecutionPlan

plan_id, gw, created_at

steps[] ordered:

{step_id, type, payload} where payload references internal player IDs + display metadata

plan_summary:

ft_before, ft_after, hit_cost, bank, chip_intent

ExecutionProgress

plan_id

completed_step_ids[]

last_active_at

status: in_progress | completed | abandoned

Success Metrics

Apply Mode adoption: % of finalized plans that enter Apply Mode.

Completion rate: % of Apply sessions marked “completed.”

Drop-off step distribution: where users quit (helps refine copy/UX).

Time-to-completion median.

Qualitative: in-app “Was this walkthrough helpful?” (1–5) after completion.

Implementation Notes (High-Level)

Recommended stack: React Native (WebView + bottom sheet overlay) or Flutter equivalent.

Navigation: two top-level screens

Plan/Analytics

Apply Mode (WebView + Overlay)

URL routing: Maintain a small mapping from “intent” → FPL page URL.

Offline behavior: Apply Mode requires connectivity; show clear state when offline.

Out of Scope (Explicit)

Automated element highlighting, DOM-driven step advancement.

Validating transfers/captain choices against FPL state.

Handling price-change remediation within execution (can be a later enhancement via planning re-entry).

MVP Cut

Transfers + Confirm + Captain/Vice + Bench order steps

Progress persistence + Resume

Replan jump-out + return

Clean UX polish (bottom sheet, player cards, step list)

This delivers a premium “execution browser” experience on mobile without auth ownership or scraping, while preserving the key loop: plan → apply → replan → apply.