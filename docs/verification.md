# Verification report — 2026-09-19

**Status: PARTIAL acceptance.** The implemented web/backend platform passes the checks below. The requested real-phone-to-backend-to-dashboard acceptance has **not** been exercised. No actual Quest client has connected. Synthetic movement and mobile viewport emulation do not close those gates.

## What was checked

| Check | Evidence | Result |
|---|---|---|
| Backend behavior | `cd backend && uv run pytest -q` — 16 tests | PASS |
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
- **Providers:** real Gemini and ElevenLabs calls require credentials and approved voice configuration; current evidence covers deterministic fallback and mocked provider behavior only.
- **Presage:** intentionally disabled; platform/access eligibility not verified. No SDK or invented vitals.
- **Impiricus:** clinician review/communication workflow demonstration only. No Impiricus API or claim of sponsor API integration.
- **Tiger Data hosted service/Timescale:** ordinary PostgreSQL is tested. Hosted credentials and Timescale optimizations are not required for this demo and are not tested.
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
