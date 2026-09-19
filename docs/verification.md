# Verification report — 2026-09-19

**Status: PARTIAL acceptance.** The implemented web/backend platform passes the checks below. The requested real-phone-to-backend-to-dashboard acceptance has **not** been exercised. No actual Quest client has connected. Synthetic movement and mobile viewport emulation do not close those gates.

## What was checked

| Check | Evidence | Result |
|---|---|---|
| Backend behavior | `backend/.venv/bin/pytest backend/tests -q` — 25 tests | PASS |
| Backend lint | `cd backend && uvx ruff check app tests` | PASS |
| Fresh PostgreSQL migration and fictional seed | Alembic `upgrade head`, seed on PostgreSQL 17 Docker | PASS |
| Actual API process restart | `scripts/verify_persistence.py`; [saved result](evidence/postgresql-restart.json) | PASS, synthetic frames |
| Duplicate ingestion | 16 initial frames accepted, same 16 accepted zero times on resend; one authoritative repetition | PASS |
| Completion | Repeated completion returns same state; one metrics record | PASS |
| Safety of state transitions | Tests: loss, pause, stale packets after resume, source isolation, sequence reconnect, pairing expiry/single use/source mismatch, unauthorized access | PASS |
| Gemini output/failure | Tests reject unsupported fact codes and numerical prose; retain deterministic report on connection failure | PASS, mocked provider |
| ElevenLabs output/failure | Tests reject unapproved cues, handle missing credentials and failed calls, cache repeated phrase | PASS, mocked audio |
| Frontend | `npm run generate:api`, `npm run typecheck`, `npm run build` | PASS |
| Dependency advisory check | `npm audit --omit=dev --audit-level=high` | PASS, zero vulnerabilities at verification time |
| Browser assignment → plan | `scripts/browser_smoke.mjs` against actual API/PostgreSQL; desktop assignment visible in 390px patient viewport | PASS |
| Browser review | Saved synthetic phone session opened; Three.js canvas, movement chart, repetition marker and playback control inspected | PASS |
| Camera unavailable | Browser reports actionable unsupported-camera guidance; no page exceptions | PASS, no physical capture |
| Responsive UI | 390px mobile viewport; no horizontal overflow | PASS |
| WebSocket schema | `uv run --with jsonschema ../scripts/validate_contract_examples.py` from backend; 14 examples | PASS |
| Unity simulator | HTTP pairing + WebSocket capture: session `251719ec-73e1-4342-bb88-e6888a51fe89`, 63 frames, 3 repetitions | PASS, simulated Quest coordinates |
| Docker stack | Isolated `arvr-smoke` project: all four services running, PostgreSQL healthy; frontend, `/api/v1/time`, `/api/docs`, `/api/openapi.json` return 200 | PASS |
| Caddy WebSocket + Docker restart | Simulator session `07c8d934-e37e-438f-a7ae-43866bf33a9f`: 18 frames and one repetition retained after backend recreation | PASS, synthetic |

The unit suite emits two upstream Starlette/httpx/AnyIO deprecation warnings, with no failing assertions. SQLite is used only in isolated unit fixtures; durability checks above use PostgreSQL and separate API processes.

## Browser evidence

- [Therapist assignment](evidence/therapist-assignment.png)
- [Patient plan, mobile viewport](evidence/patient-plan.png)
- [Saved session review and replay](evidence/session-review.png)
- [Camera unavailable handling](evidence/camera-unavailable.png)

The short replay fixture contains only right shoulder, elbow and wrist; its three-joint rendering is intentional. Real MediaPipe capture sends the documented joint set. Screenshot data and patients are fictional/synthetic. Camera-unavailable checks create empty sessions but no fabricated observations.

## Issues found and fixed

- Added typed OpenAPI responses and generated frontend types to catch cross-layer shape mismatches.
- Isolated device streams and chose one persistent authoritative device; secondary tracking status cannot reset its counter.
- Rejected stale buffered capture after resume and prevented mixed simulated/real-device pairing.
- Fixed repetition marker filtering to match device IDs, plus Quest simulator coordinate labels.
- Prevented a phone from consuming a headset pairing code accidentally.
- Replaced unvalidated Gemini prose with allowed fact selection and server-rendered claims.
- Made camera errors actionable and kept optional audio failures independent.
- Overrode the affected PostCSS dependency; final production dependency audit is clean.

## Remaining unverified areas and boundaries

- **Physical phone:** camera permission, MediaPipe model execution on mobile hardware, actual person movement, backgrounding/interruption and HTTPS/WSS tunnel behavior. Automated unavailable-camera checks are not physical-phone validation.
- **Actual Quest:** teammate Unity application, hardware timestamps, local coordinate origin, target placement and live hand tracking. Simulator integration is verified separately.
- **Providers:** live Gemini and ElevenLabs calls now pass (see follow-up evidence below). Fallback remains expected during provider errors/timeouts; uninterrupted provider availability is not promised.
- **Presage:** intentionally disabled; platform/access eligibility not verified. No SDK or invented vitals.
- **Impiricus:** clinician review/communication workflow demonstration only. No Impiricus API or claim of sponsor API integration.
- **Tiger Data hosted service/Timescale:** hosted connection, migrations, seeding and authenticated API reads are now verified (details below). Hosted synthetic movement/restart and public HTTPS/WSS flows now pass; physical capture and Timescale-specific optimizations remain unverified.
- Rate limits and speech cache are process-local; deployment is a single backend worker. No registration/password-reset, clinical validation, archival retention system or production health-record compliance claim is included.
- MediaPipe WASM/model download requires the documented CDN unless assets are self-hosted.

## Real-phone acceptance checklist

1. Follow [HTTPS setup](local-https.md), choose private seed credentials, and use the same public HTTPS origin on laptop and phone.
2. Log in as therapist, create an assignment, then open it as the patient on a **physical phone**.
3. Grant camera access and record seated right-elbow bend/extension with visible joints. Exercise pause/resume, hide the arm, background/return, and briefly disconnect/reconnect. Confirm counters do not advance during invalid tracking or pause.
4. Finish, submit a check-in and note the session UUID. Confirm it is not marked synthetic.
5. Restart backend, reopen the therapist session detail, and inspect saved pose replay, events, quality, notes and report.
6. Record phone model/browser, HTTPS origin, session UUID, observed results and screenshots here. This gate remains open until that evidence exists.
7. Separately pair the actual Unity client using [the versioned contract](unity-interface.md) and document the headset/device result.

## Reproduce automated checks

The PostgreSQL restart script requires an already migrated and seeded **test database** and creates labeled synthetic records without deleting data:

```sh
cd backend
DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST:PORT/DB' uv run python ../scripts/verify_persistence.py
```

Install Playwright in an isolated tools directory and run `scripts/browser_smoke.mjs` with `PLAYWRIGHT_MODULE` set to its absolute `playwright/index.mjs`, `TEST_ORIGIN` pointing to the running web app, and `DEMO_PASSWORD` matching the seed if customized. Optionally set `REVIEW_SESSION_ID` to a saved synthetic session. Screenshots default to `/tmp/arvr-browser-evidence`. This test creates an assignment and an empty camera setup session.

## Tiger Data hosted setup

Follow-up setup used the configured hosted service, after checking that its public schema had no existing tables. Alembic upgrade to `405e2f264a53` succeeded, creating all 12 application tables plus `alembic_version`. No existing tables or records were dropped.

Seeded two fictional users (`therapist@demo.local`, `patient@demo.local`), one fictional patient, one therapist access relationship, one seated-reach exercise and one five-repetition assignment. Passwords use the private `DEMO_PASSWORD` from the local environment and are stored as hashes. Running the seed again left all row counts unchanged.

FastAPI TestClient against the actual hosted database verified both account logins, the therapist's patient list, the patient's five-repetition assignment, and denied unauthenticated patient-list access. No tokens, passwords or connection URLs are included in this evidence.

At initial seeding, movement tables were empty. Follow-up verification below subsequently created explicitly synthetic sessions plus empty browser setup sessions; no physical movement is claimed.


## Combined-mode and live integration follow-up

**Status: PARTIAL hardware acceptance; implemented backend/browser changes verified.** The rebuilt Docker project `arvr-tiger` uses hosted Tiger Data on loopback gateway 8081, exposed through the temporary public HTTPS origin in private `.env`. The original local smoke stack remains separate.

| Check | Commands / evidence | Result |
|---|---|---|
| Backend regression and combined behavior | `backend/.venv/bin/pytest backend/tests -q`: 25 tests; independent streams, geometry/aspect, hidden joints, stale setup, disconnected camera expiry, headset resume ownership, idle socket controls, deduplication | PASS |
| Lint and contracts | `uvx ruff check backend/app backend/tests scripts/verify_providers.py scripts/verify_combined.py`; regenerated OpenAPI/types and WS schema; 14 examples validated | PASS |
| Frontend / containers | Typecheck and production Docker builds; backend/frontend/gateway recreated and running | PASS |
| Hosted phone recording/restart | [tiger-restart.json](evidence/tiger-restart.json): 16 accepted frames, one repetition, zero accepted duplicates, identical replay/report after process restarts | PASS, synthetic |
| Combined public HTTPS/WSS | `scripts/verify_combined.py`; [tiger-combined.json](evidence/tiger-combined.json): independent phone trunk and Quest hand-target streams, setup gate, headset pause/resume/finish, one authoritative cycle, persisted grounded report | PASS, synthetic |
| Data after container recreation | First combined test session retained 38 frames, one repetition and its Gemini report after backend/frontend recreation | PASS |
| Live Gemini | `scripts/verify_providers.py`; [live-providers.json](evidence/live-providers.json): validated fact selection from `gemini-3.6-flash`; combined reports exercised both live-model and deterministic fallback paths | PASS |
| Live ElevenLabs | Same script: successful nonempty output with valid MP3 header from available premade Sarah voice | PASS, generated audio; human listening not checked |
| Public browser workflows | `scripts/browser_smoke.mjs`; [tiger-browser.json](evidence/tiger-browser.json): login, assignment, mobile plan, playback, both combined tracks, camera setup gate, phone audio absent in combined mode, Quest-only emergency pause/finish and check-in | PASS, browser automation |
| Visual checks | [combined setup](evidence/tiger-browser/combined-setup.png), [trunk replay](evidence/tiger-browser/combined-trunk-replay.png), [Quest browser controls](evidence/tiger-browser/quest-controls.png); setup and trunk replay images inspected | PASS |

### Issues found and fixed

- The old Gemini model returned HTTP 404 for this account. Changed the default and private config to an available model. A diagnostic HTTP 200 exposed a schema mismatch: Gemini sometimes selected globally allowed codes that did not apply to the current session. Validation correctly rejected those responses. Restricted the outgoing JSON schema enum and list length to the actual session facts, added a regression test, and configured minimal thinking for bounded fact ordering. The bounded timeout and deterministic fallback remain in place.
- The configured ElevenLabs voice did not exist. Selected a premade voice actually returned by the account's voice API and verified generated MP3 output.
- Added explicit combined mode and separate 2D trunk observations/review flags. These flags are not clinical compensation diagnoses; camera alignment affects them. No new database migration was required because the existing JSON frame/config/state columns hold the additional fields.
- Combined sessions start paused and require fresh, continuously visible shoulder/hip tracking before resume. Phone tokens cannot resume headset modes. Backend repetition counting remains authoritative in every mode.
- Headset modes disable browser voice guidance. Idle WebSockets receive other-device state changes; phone polling reflects headset pause/finish. Disconnected phone readings expire instead of appearing live indefinitely.
- Added browser wake-lock request/fallback instructions and a documented maximum 10 Hz capture with 250 ms upload timer. Stop drains its queue before completion; remote completion warns about unacknowledged samples.
- Isolated provider environment variables in unit fixtures so running tests from repository root cannot accidentally make live paid calls.
- Browser verification initially read replay options before the async replay loaded; added an explicit wait and reran successfully.

### Remaining unverified areas

Actual phone camera/model execution, on-device wake lock and interruptions, Unity's in-headset controls/audio/passthrough, physical Quest tracking, a stable named domain, hotspot rehearsal and a previously recorded real-session backup remain pending. The backend supports headset commands, but this repository does not contain the teammate's Unity application. See [demo operations](demo-operations.md) and [the Unity integration handoff](unity-interface.md#combined-mode-and-room-setup). Presage, Impiricus API integration and Timescale hypertables/continuous aggregates are not implemented by this change.

After deploying the fact-schema repair, the authenticated public API regenerated the latest synthetic combined report with `gemini-3.6-flash` and returned HTTP 200 with 66,499 bytes of ElevenLabs audio. See [deployed provider evidence](evidence/deployed-providers.json). The earlier combined-run evidence preserves its original fallback result; the subsequent report refresh is recorded separately.


## Quest Browser and inspectable correction follow-up

**Status: PARTIAL — software/protocol verified, physical Quest 3 acceptance pending.** Added a WebXR client at `/quest` with required passthrough/hand tracking, an initially aligned stable floor origin, spatial target and return shell, in-headset controls, bounded acknowledged sampling, optional voice, origin-reset protection and an unsupported-browser gate. This is a browser alternative; the teammate's native Unity project is still outside this repository.

| Check | Evidence | Result |
|---|---|---|
| Backend | 28 passing tests, including missed target → correct reach, deduplication, tracking loss and correction cue with attempt ID | PASS |
| Code/contracts | Ruff; generated REST/WS contracts and frontend types; 14 schema examples; frontend typecheck and Docker production build including `/quest` | PASS |
| Coordinates | Executed WebXR-to-Quest handedness conversion and nonfinite-input rejection | PASS, mathematical check |
| Hosted correction flow | [quest-correction.json](evidence/quest-correction.json): simulated best distances 0.21 m (target not held) and 0.06 m (completed) against 0.12 m target, linked adjustment cue and one repetition | PASS, synthetic |
| Browser | [quest-browser.json](evidence/quest-browser.json): unsupported desktop XR blocked, missed/successful replay buttons seek different saved intervals, report preserves both evidence IDs and playback works; screenshots inspected | PASS |

Each classified attempt is stored in its observed movement frame with device/sequence identity, timing, threshold and best observed value. A report carries those evidence objects. Camera/hand loss does not invent a miss or success. Pause/resume discards partial attempts; unfinished attempts are not classified as failed movement. UI flags say “target not held”, not clinical form correction. Gemini selects a corresponding allowed fact code, with all evidence derived from saved data.

The headset renderer, right-hand tracking, pinch targeting, passthrough, world alignment, headset removal, reset handling and audio **have not run on physical Quest 3 hardware here**. No Unity installation or ADB executable was available locally. Desktop browser tests do not exercise immersive rendering. Follow [the hardware acceptance steps](quest-browser.md) before claiming the complete real-person correction loop works. No measured accuracy comparison or clinician validation has been performed.
