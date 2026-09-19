# Engineering plan and acceptance evidence

Build the smallest complete seated-reach workflow: therapist assignment → authenticated phone plan → real browser landmarks → durable session → therapist review. Real phone acceptance and actual headset acceptance are separate gates. A simulator cannot satisfy either.

## Delivery sequence

1. PostgreSQL schema, incremental Alembic migration, authentication/access checks, clearly fictional users and catalog.
2. Therapist assignment and patient plan, linked by assignment ID.
3. Browser MediaPipe, permission/setup flow, acknowledged bounded transport and durable chunks.
4. Deterministic reach/return state machine with holds, hysteresis, visibility rejection, pause and gap resets.
5. Actual-frame Three.js replay, measurements, repetition markers, missing/inferred tracking labels, notes and saved report.
6. Versioned Unity protocol, pairing and explicitly synthetic simulator; test the actual headset separately.
7. Optional grounded Gemini summaries and cached approved ElevenLabs cues; provider failure leaves measurements intact.
8. Presage remains disabled until platform support/access are verified.
9. Automated API/frontend checks and manual real-phone/restart acceptance; record evidence and blockers honestly.

## Parallel ownership and integration

| Workstream | Ownership | Dependencies and exit evidence |
|---|---|---|
| Backend | `backend/` | Publish request shapes early; PostgreSQL migrations, authenticated API, tracking logic and focused tests |
| Browser apps | `frontend/` | Follow published REST/WS shapes; build/typecheck; camera and review routes |
| Contracts / operations | `contracts/`, documentation, simulator, Compose/Caddy | Derive schemas and instructions from executable implementation; validate sample messages |
| Integration / review | Root coordinator, verification report and CI | Test real PostgreSQL, restart persistence, authorization, duplicate packets, pause/loss, reconnect and provider failure; resolve cross-stream mismatches |

Workers share one branch/workspace, do not revert each other, and keep Unity files outside their ownership. Independent work is parallel; contract changes are coordinated before integration. A dedicated branch is pushed without force; PR states exact tested scope.

## Measurement decisions

Phone mode measures projected elbow extension in an aspect-corrected image plane, with configurable reach/return thresholds. It does not measure hand-to-Quest-target distance or calibrated depth. Quest mode measures right wrist distance to a configured target in a stable Quest local space, in meters. Backend owns the authoritative repetition count in both modes; Unity events retain their source but cannot double-count repetitions. Coordinates from devices are never averaged. Calibration and sensor fusion are outside this demo.

Thresholds are demonstration settings, not universal clinical norms. Patient notes and check-in ratings remain separate from inferred metrics. Synthetic data is explicitly labeled. No seeded capture masquerades as a completed real session.

## Completion gates

Automated acceptance covers persistence/restart, authentication, session access, pairing, deterministic repeats, loss/pause, sequence deduplication, reconnect and provider fallback. Human acceptance must create an assignment on the dashboard, open it on a physical phone through HTTPS, capture actual movement, finish, restart the backend and review the same saved session. Record phone model/browser, origin, session ID and evidence in `docs/verification.md`. Only actual teammates' headset connection can close the Unity acceptance gate.

## Integrated results

| Workstream | Status | Delivered evidence |
|---|---|---|
| Backend | Implemented and locally verified | 16 focused tests, PostgreSQL migration and process restart |
| Browser apps | Implemented and locally verified | Production build/typecheck, assignment-to-plan browser check, replay screenshots |
| Contracts / operations | Implemented and locally verified | 14 schema examples, synthetic Unity client, Docker/Caddy WebSocket session |
| Physical acceptance | Pending hardware/credentials | Real phone, real Unity headset client and live optional providers remain separate gates |

Resolved integration mismatches include typed REST responses, authoritative per-device tracking, pairing source checks, buffered-frame pause boundaries, and device-based replay event markers. Detailed evidence and next physical acceptance steps are in [verification.md](verification.md).
