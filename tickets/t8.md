# A8: Project settings, model selection, and OpenAI API connection status

**Status:** Implemented and verified on 2026-10-20. Provider/model/effort and health checks used controlled HTTP fixtures; live billing/quality is unverified. See `docs/STATUS.md` for actual checks and limits.

## Purpose and design invariants

Make **Create Project** and **Edit Project** two modes of a *single, well-designed project-settings experience*. Introduce curated AI model selection and project-specific reasoning ("Thinking level"), while preserving the already working project creation, strategies, provenance, research modes and local persistence.

Show an unobtrusive, **truthful OpenAI API connection indicator at the top right** of the application. This is the API authenticated with SIGMA's key, **not** the user's ChatGPT web-app login. Use familiar connection-status UI conventions (small status dot + plain-language label, optional details/retry), not a decorative indicator that is green simply because a variable is populated.

**Preserve approved visual decisions:** The exact Home art, A5 workspace metallic brand, and enthusiastically accepted A7 Strategies layout are locked. Neither needs a redesign or regenerated art. Exercise independent aesthetic judgment about spacing, dialog hierarchy, pencil location, and header balance; do not mechanically attach controls without reviewing the whole experience. No artwork handoff is required for A8.

## 1. One shared Create/Edit Project form

- **New Project** on Home continues opening the project form, but its exact visible dialog **header is "Create Project"**.
- On the project workspace, place a small, tasteful **pencil icon immediately beside the visible project name** (the main project heading, not an inert gear/settings destination). It is a real button with an accessible name such as **Edit Project** and appropriate hover, keyboard focus, 44px-ish hit area without a bulky appearance, and a sensible layout at desktop/mobile. Clicking it opens the same form with exact visible header **"Edit Project"**.
- Use a shared form component/field definitions and consistent dark-navy/copper styling, spacing, validation, help, keyboard handling, Escape/Cancel, first-field focus and return-to-trigger focus. Avoid drifting into two nearly-but-not-quite matching forms.
- Both modes expose, in the same logical order:
  1. **Project name** (required, prefilled in Edit);
  2. **Research problem** (required multiline, prefilled in Edit);
  3. **Research mode** dropdown: `Default`, `Mathematical` (editable in both directions);
  4. **AI model** dropdown: curated research-capable choices described below;
  5. **Thinking level** dropdown: default **High**, editable independently of model.
- Creation continues to preview the derived **read-only destination** from A6 and create inside the configured projects root; editing never asks for a path or moves/renames a directory. Changing the *display name* has no effect on the directory name.
- **Create Project** / **Save Changes** are the affirmative actions, paired with **Cancel**. Edits must persist as one validated transaction when Save Changes is clicked; no save-on-blur, per-keystroke persistence, or save-on-close. A no-op Save should not create a spurious event or rewrite files.
- On Save, close the dialog and update the project heading and visible details without leaving the project workspace; give discreet success feedback and return focus. If persistence fails, leave edited values intact and present a recoverable error. Creation still navigates into the real new project.
- Preserve the **stable existing `project.id` UUID**. The current code already generates it with `uuid4()` and validates it on load; **do not add a second GUID**. Show it unobtrusively in Project details if useful. It must survive title, problem, research mode, model and thinking changes. Project path/slug is a location, not an identity.

## 2. Curated AI model dropdown, not the whole account catalog

OpenAI's `GET /v1/models` provides accessible model IDs and basic metadata, **not** suitability, pricing, structured-output support or reasoning levels. A user's account may list hundreds of specialized, legacy, snapshot and non-generative models. Do **not** dump that raw list into the UI or filter merely by `gpt-` prefix.

- Implement a small **server-maintained capability catalog** of explicitly reviewed models suitable for *SIGMA's actual Responses API strategy proposal flow*: authenticated API access, standard text input/output, structured JSON schema response, and supported reasoning effort. Prefer stable aliases to dated snapshots.
- Starting candidate shortlist from the user's actual account list: `gpt-6-luna` (Economy), `gpt-6.1-sol` (Balanced), `gpt-6-astra` (Advanced). **Validate** official capabilities, endpoint and reasoning-effort compatibility; do not claim support solely because an ID occurs in `/v1/models`. Include only verified compatible candidates; if a claimed model/effort combination fails, display a clear incompatibility and don't silently substitute another model or drop reasoning.
- Fetch the account's model IDs from OpenAI **in the Python backend** with its server-held API key, via a bounded and cached request. Intersect the results with the curated catalog; return only safe labels, IDs, descriptions, supported thinking options and relevant availability to React. No provider credentials or unreviewed models in frontend configuration.
- Present meaningful choices with descriptive labels, e.g. **Sol · Balanced**, **Luna · Economy**, **Astra · Advanced**, and perhaps concise help explaining quality/cost tradeoffs without unverified or stale numerical pricing. An unavailable previously selected model stays displayed, flagged unavailable, until the user intentionally changes it. Do not alter a stored choice because the catalog changed or the provider is temporarily unreachable.
- Default for **new** projects: **Sol (gpt-6.1-sol) + High**, **provided that combination is verified accessible and supported**. If not, use a documented, genuinely supported default and clearly disclose it; no hidden fallback after a user selects a different model. Consider `SIGMA_AI_MODEL` a compatibility/bootstrap override for older deployments, **not** the primary persisted per-project configuration.
- When the API is temporarily offline, do not erase stored settings or force changes; offer cached/known catalog entries with their availability qualified, and allow saving project metadata without requiring an outbound API call. Do not imply that a model is verified reachable when it isn't.
- If the documented model catalog has zero supported choices, explicitly surface the setup/blocker. Keep manual strategies working; don't silently promote an arbitrary non-reasoning or deprecated model.

## 3. Thinking level

- Store each project's requested reasoning effort as a persisted setting, defaulting to **`high`**. Present human-facing **Low, Medium, High, Extra high** options only when valid for the selected model; do not include unsupported combinations (some models may support only certain efforts). If another documented model supports other named levels, extend the catalog deliberately.
- Use the actual API parameter `reasoning: { effort: "high" }` (or its appropriate level) in the Responses API request **when supported**. Reasoning effort is an API setting, **not** a ChatGPT/Codex UI setting. Do not treat `max_output_tokens` as independent of thought budget: high reasoning can consume output-token budget; review A7's 3500-token limit and adjust bound/documentation carefully rather than causing avoidable incomplete responses.
- Client and backend must both enforce compatible model/effort pairs. If the user switches to a model not supporting a selected effort, offer a clear user-visible correction, not an undisclosed normalization. Never send an unsupported combination to the provider or silently fall back to lower effort.
- Settings affect **future AI requests only**, not earlier strategies or their recorded provenance. Retain the actual model identifier used on each accepted AI proposal. Persist the requested reasoning level with new proposal provenance if appropriate to the schema; never invent missing past metadata.
- Do not implement per-strategy settings, autonomous agent thinking loops, or cost accounting in this assignment.

## 4. Persisted settings and atomic project editing

- `src/sigma/projects.py` currently uses strict versioned JSON (A7: schema **v5**), project fields including `id/title/problem/research_mode/active_order`, immutable audit events and staged atomic file replacement. Build on these mechanisms with a deliberate next schema version (likely **v6**) storing all project-level configuration: title, problem, research mode, model ID, and reasoning effort. Do not put settings in a separate editable file or make environment variables the sole source of project choices.
- Historical v1–v5 projects must open with a sensible legacy default for missing settings, **without modifying their bytes just because they were opened**. When first edited, migrate safely under the existing backup scheme; preserve all strategies, stages, ordering, prior events, UUIDs and archive/removed strategies. Validate strict schema and event consistency; do not weaken parsing to swallow unknown fields.
- Add a project-update operation to shared Python services, FastAPI and CLI as appropriate. Return the new complete `ProjectView` and integrate with existing frontend state. Record a meaningful **`project.updated`** event including the actual old/new setting changes, sufficient for the existing project-history audit to explain edits. Ensure immutable identity and path. Keep the audit readable, avoid duplicate/no-op events, and verify full integrity on load.
- Serialize **on each explicit successful change**, not at Close Project. Current `_update_project` performs locking, validation, staging and atomic `os.replace`; reuse it. Reject stale concurrent edits or demand explicit refresh/retry, rather than silently overwriting a second editor's settings.
- The existing `close_project()` is a no-op for stored state: **Close Project means return to Home**, with no save, flush, delete, session teardown or background-work termination. Do not introduce a confirmation now when nothing is running.
- **Future agent behavior:** when project agents actually exist and are running, a Close Project interaction should explain the active work and request confirmation/clarify whether agents continue. Do not implement an imaginary runner/confirmation in A8. Record this future requirement in design notes/README as appropriate. Closing the UI must not implicitly cancel work.

## 5. Real top-right OpenAI API status

The user wants a recognizable small connection-health affordance at the **upper right** of both Home and the project workspace. Respect the existing header composition; keep it legible but quiet rather than adding a large alert/banner that fights the approved art. Prefer a standard **status dot + short label** pattern with concise optional explanatory detail / Retry action.

**The text should say "OpenAI API", not "ChatGPT"**: API-key authentication is distinct from a ChatGPT subscription/login.

Status semantics must be grounded in a real provider check:

- **Checking:** muted/neutral dot with "Checking OpenAI API…" (or equivalent); no premature green.
- **Connected:** **green dot** plus "OpenAI API connected" only after the backend successfully authenticates to a suitable endpoint such as `GET https://api.openai.com/v1/models` with an HTTP 200 and valid response. Clarify in tooltip/details that this verifies API authentication/reachability **only**, not selected-model generation, credits, quota or billing.
- **Missing/unconfigured:** neutral/amber dot and "OpenAI API not configured" with actionable local server `OPENAI_API_KEY` / `SIGMA_AI_ENABLED` guidance. Avoid marking mere missing key as an internet outage.
- **Invalid key/authentication failed (401/403 as appropriate):** red dot and "Can't connect to OpenAI API · Check API key" (or equivalent). On 403, use accurate wording for key/account permissions rather than asserting the key itself is invalid.
- **Network error/timeout/provider 5xx:** amber/red as warranted with "OpenAI API unavailable · Check connection" / "Try again"; don't misleadingly blame the key. 429 is rate/quota-limited and must be classified separately from bad credentials.
- **Unknown/offline/stale:** gray/amber with an honest timestamp if previously checked; never show stale success as if it were current.
- No unnecessary repeated flashes or aggressive polling. Check on initial app load (or first relevant entry), cache with a bounded TTL, refresh on user request and after meaningful retry; avoid one provider call per React render, typing event or route transition. No model-generation request or paid tokens should be spent merely to light the dot.
- Python server endpoint exposes **only** classified status, last checked time and safe human-readable guidance. Never expose the API key, Authorization header, secret fragments, raw provider errors that might echo secrets, or complete response headers/body to the browser. Implement HTTP limits, trusted endpoint, request coalescing, timeout and bounded size. No keys in `VITE_` variables. Don't log secrets.
- Accessible status: readable text accompanies color, `role="status"` / polite live region for meaningful state changes without repeated noisy announcements, sufficient contrast, keyboard-accessible Retry/details where provided, and usable layout at 320/390px. Do not render the status as a colorful badge or generic success callout.

**Distinguish connectivity from feature readiness.** A7's current `/api/projects/proposals/config` marks `available` true based on *environment variables alone* (no network check). Revise/configure its semantics so generation readiness depends on selected project's model/effort eligibility and server setup, without claiming the account/model is verified simply because a key is present. Network connectivity checking and a real generation result are separate levels of proof.

## 6. A7 integration and configuration transition

- A7's `src/sigma/proposals.py` currently selects a global `SIGMA_AI_MODEL` (default `gpt-4.1`) and posts directly to `/v1/responses` with a JSON-schema payload; it does **not** currently send a `reasoning` parameter. Update it to obtain **the project model and effort from persisted project state** at the moment the user requests Generate with AI, while retaining opt-in consent, server-only key, timeout, concurrency gate, context bounds, duplicate detection, structured validation, receipt/provenance and draft-before-save.
- Treat the selected model/effort as part of the generation request's immutable metadata so a simultaneous settings change cannot misattribute the response. Preserve accepted proposal receipts' project-ID matching and avoid revising old strategies when settings change.
- Prefer `.env` sourcing/configuration conventions already documented by SIGMA; no auto-writing or storing the API secret in `project.json`. Include `.env.example` only if useful and ensure `.env` remains gitignored.
- Document which environment variables remain necessary, particularly `SIGMA_AI_ENABLED` and `OPENAI_API_KEY`, and how `SIGMA_AI_MODEL` relates to stored project settings after the transition. Key/billing management is deliberately server-level; model/effort is project-level.
- Preserve A7's manual path, status/reorder UI, provenance and full history. No agents should start or stop when project settings change.

## 7. Verification and definition of done

1. **Inspect before modifying:** current A7 code, schema migration rules, all Home/workspace/form CSS, browser tests and `docs/STATUS.md`. Preserve exact approved art and correct frontend use of assets.
2. **UI:** browser-test shared form with **Create Project** and **Edit Project** headings, project pencil click/focus/cancel, identical fields/order, current values, save/error/retry, long titles/problems, responsive layouts and no Home/Strategies visual regressions. Confirm the project UUID and directory remain stable after title edit; changing mode/model/effort does not reset strategies or history.
3. **Persistence:** create + reopen with explicit model/High; edit + reopen with changed model/effort/mode; verify atomic transaction and `project.updated` audit, legacy v1–v5 compatibility/no-write reads, no-op edits, exact migration backups, injected save failure, concurrent edit conflicts, malformed input and unsupported values.
4. **Model discovery:** fake/captured HTTP fixtures for valid /v1/models, unsupported IDs, missing selected IDs, unavailable provider, 401, 403, 429, 500, network failure/timeout, stale cache and refresh. Confirm a raw account catalog cannot inject unsupported UI choices.
5. **Real integration:** generate with the selected **per-project** model and actual compatible `reasoning.effort`; verify raw outgoing request in controlled HTTP fixtures, including High. Confirm no mutations before user approval and provider errors preserve drafts. Do not assert live provider tests unless actually performed, and never make billable requests without explicit user approval.
6. **Connection UI:** browser-check small top-right indicator on Home and workspace; normal checking/connected/unconfigured/unauthorized/offline states, safe detail/retry, status text + dot (not color alone), no leaks, no unbounded polling, no layout shifts.
7. **Commands:** run `./sigma test`, frontend type/build, CLI/API scenarios and real desktop/mobile browser checks. Compare Home artwork and workspace screenshots against accepted A6/A7 baselines. Update `docs/STATUS.md`, relevant configuration docs/README and deliberate commit if checks pass; report precise tests and unresolved limitations rather than claiming success by inspection only.

**Definition of done:** SIGMA has one polished project form titled **Create Project** or **Edit Project**, with an accessible pencil next to the project name; project UUID remains stable and all settings (name, problem, research mode, curated model, **High** default thinking level) persist. AI generation uses the saved project's supported model/effort. A small green status dot at top right reports a **real verified OpenAI API connection**, with truthful alternatives when unavailable. Close Project still simply returns Home and never serves as a save button.
