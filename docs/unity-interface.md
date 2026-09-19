# Unity / Meta Quest interface — version 1

The teammate-owned Unity application remains outside this implementation; the backend and phone/browser modes below are implemented, while in-headset controls must be wired and tested in that app. `scripts/unity_simulator.py` is a **synthetic protocol client**, not a headset integration or clinical capture. Actual Quest connection, coordinate alignment and hardware behavior require separate verification.

## Connect and authenticate

Use the external HTTPS origin from the team; never a laptop `localhost` URL. REST uses `/api/v1`; WebSocket URL is `wss://PUBLIC_HOST/api/v1/ws/SESSION_ID`. Runtime REST docs and the exported OpenAPI document define exact HTTP bodies. A therapist or the assigned patient authenticates with `/auth/login`, receiving a bearer token. Patient access and therapist-patient links are checked on session operations.

1. The authenticated browser creates a session with `POST /sessions` and body `{"assignment_id":"…","mode":"quest","is_synthetic":false}`. The server snapshots the assignment's exercise configuration.
2. It requests `POST /sessions/SESSION_ID/pairing` with `{"source":"quest"}`. Display the short-lived code to the patient. Codes expire after five minutes, are single use, and are session scoped. Pair exchanges are limited to six per minute per remote IP; issue requests to ten per minute per user. The first phone device in phone mode, or Quest device in Quest/combined mode, becomes the authoritative input stream; the backend counts repetitions. Other devices may pair as separate observation streams; they never update the repetition counter.
3. Unity sends `POST /devices/pair` with `{"code":"DISPLAYED_CODE","label":"Quest headset"}`. This exchanges the secret code for `device_token`, `device_id`, and `session_id`. Do not use the therapist's bearer token on the headset.
4. Connect the WebSocket and immediately send `device.join` containing the device token. User bearer tokens expire after eight hours and session-device tokens after four hours. Tokens are not URL query parameters and must not be logged. A token for a different session must fail.
5. Wait for `session.config`; only then begin streaming and keep receiving messages while sending. Unity may give immediate local visual/haptic feedback, but backend repetition count is authoritative.

## Envelope and time

Every client message is JSON: `{"version":1,"type":"…","id":"unique-request-id","payload":{…}}`. Client IDs are nonempty strings up to 100 characters. JSON messages are limited to 64 KiB; join must arrive within ten seconds. Use UUIDs. Types discriminate the versioned schema in [`../contracts/websocket.v1.schema.json`](../contracts/websocket.v1.schema.json). The frame's `seq`, not envelope ID, provides durable movement deduplication. Client exercise events use their own `seq` plus `name` for deduplication and are retained as non-authoritative with a `local:` name prefix to avoid authoritative-event collisions. Capture timestamps are ISO 8601 with timezone, preferably UTC, such as `2026-09-19T14:00:00.100Z`; sequence numbers increase per device, beginning at zero.

`captured_at` is capture time, not delayed transmission time. Fetch `GET /api/v1/time`, which returns `server_time` in UTC. Estimate device clock offset from that round trip (**device time at the midpoint minus server time**, in milliseconds); send `clock_offset_ms` through `device.status`. An estimate is metadata, not proof of synchronization. Preserve device streams independently. Do not infer physical correspondence or average phone/Quest positions.

## Client messages

| Type | Payload | Purpose |
|---|---|---|
| `device.join` | `{"token":"SESSION_DEVICE_TOKEN"}` | First message, authenticate connection |
| `device.status` | `{"clock_offset_ms":0,"tracking_valid":true}` | Clock estimate and device tracking status |
| `tracking.frame` | Frame below | Observed landmark sample, or explicit invalid sample |
| `exercise.event` | `{"seq":0,"name":"unity_local_reach_complete","occurred_at":"2026-09-19T14:00:00Z"}` | Preserve client event provenance; never increments authoritative counter |
| `session.pause` | `{}` | Stop counting; discard partial repetition |
| `session.resume` | `{}` | Re-arm from an observed return position |
| `session.complete` | `{}` | Idempotent finish and persist summary metrics |

Example Quest frame:

```json
{"version":1,"type":"tracking.frame","id":"frame-42","payload":{"seq":42,"captured_at":"2026-09-19T14:00:00.100Z","coordinate_system":"quest_local","units":"meters","tracking_valid":true,"joints":{"right_wrist":{"x":0.04,"y":1.0,"z":0.5,"visibility":1.0,"inferred":false}}}}
```

`quest_local` is a stable Unity/Quest tracking origin in meters: x right, y up, z forward (Unity convention). `quest_target_m` must be defined in that exact same origin. Recentring changes the origin; pause, re-establish the target and start a fresh configuration/session rather than continuing with a shifted target. Do not submit world coordinates from an unrelated scene transform without converting them into the declared tracking origin. No cross-device calibration is implemented.

The seated-reach Quest criterion (also used in combined mode) is Euclidean right-wrist-to-target distance. The configuration contains `quest_target_m`, `quest_reach_m`, `quest_return_m`, `hold_ms`, `visibility_min`, and `gap_ms`. The demonstration defaults require a held return, held reach, and held return to complete one repetition; they are configurable exercise settings, not clinical norms. Send actual wrist positions. Untracked or inferred wrists are invalid; do not synthesize observations from the headset pose.

Phone frames instead declare `coordinate_system:"image_normalized"`, `units:"normalized"`, actual `image_width` and `image_height`, and `right_shoulder`, `right_elbow`, `right_wrist`. x goes right, y goes down, both normalized to the source image before any mirrored display. Optional MediaPipe z is uncalibrated and never meters. The backend calculates the elbow angle after aspect-ratio correction, labeled **projected 2D elbow degrees**. It cannot be substituted for Quest hand-to-target distance.

Joint names use snake_case anatomy: `nose`, `left_shoulder`, `right_shoulder`, `left_elbow`, `right_elbow`, `left_wrist`, `right_wrist`, `left_hip`, `right_hip`, `left_knee`, `right_knee`, `left_ankle`, `right_ankle`. Extra named joints may be recorded (up to 64); only mode-required joints participate in the exercise. Each joint has finite x/y, optional finite z, visibility 0–1, and an `inferred` boolean. Missing joints are absent, never filled with default measured positions. To mark lost tracking, send `tracking_valid:false` and `joints:{}` while preserving coordinate metadata and sequence.

## Acknowledgements, reconnect and backpressure

`session.config` answers join and identifies immutable configuration, mode and `authoritative_counter:"backend"`. `session.state` acknowledges commands using `payload.ack_id`, and supplies authoritative status/phase/count/measurement/tracking validity. `exercise.feedback` carries `{message,cue_id}` (`reach` or `tracking_lost`) after the frame acknowledgement when a repetition is recorded or tracking becomes invalid; `session.summary` is the completion reply; `error` reports rejected messages. Consult the JSON schema for server payload shapes.

Keep a bounded queue of unacknowledged frames. Start around 10 Hz; do not send the full render rate. Drop old unsent frames when the queue limit is reached, preserve sequence gaps and display degraded tracking. Never fill a dropped interval with fabricated observations. REST batch ingestion supports up to 60 frames per request when using the device-scoped bearer token.

On reconnect, reuse the same unexpired device token and `device.join`, then replay only unacknowledged frames with their original sequence numbers and capture timestamps. Duplicate/older sequences are discarded. Continue new samples with higher sequence numbers; do not reset a device sequence on a new socket. Device tokens expire. A new paired device is a separate stream and must not silently replace the authoritative device. Finish the old session from the authenticated browser and create a fresh session when its authoritative device token expires; in-place token renewal is not implemented. A gap resets a partial repetition; do not assume phase continuity across disconnects. Current status is returned by the server; never automatically resume a paused session. An already completed session cannot resume or accept additional observations, and repeated completion returns the saved completion state.

Frame acknowledgements follow database commit. Send pause/complete only after draining acknowledged frames. A server restart retains sessions, frames, device sequence and exercise state in PostgreSQL; local unacknowledged buffers remain the client's responsibility. The demo runs one backend worker; distributed fan-out and durable outbound command delivery are not implemented.

Authorization failures reject the join; expired tokens require pairing again. Schema/type/version violations produce an error instead of measurements. Oversized messages/queues are bounded. Invalid frame geometry is retained as invalid tracking or rejected; no default measurement is substituted. Session-state conflicts use HTTP 409 on REST; authorization uses 401/403, missing resources 404, invalid bodies 422 and pairing rate limits 429. Client code should display the returned error text and stop retrying non-retryable authentication/validation errors.

## Synthetic simulator

Install backend dependencies and `websockets`, then run:

```sh
python scripts/unity_simulator.py --origin https://YOUR_PUBLIC_HOST --assignment-id ASSIGNMENT_UUID
```

It signs in as the fictional patient, creates `is_synthetic:true`, requests a `simulator` pairing code, and generates deterministic Quest-local positions. It prints the resulting session ID. Optional `SIMULATOR_PASSWORD` overrides its demo password. Laptop-only automation may explicitly use `--origin http://127.0.0.1:8000 --allow-local-http`. This flag does not create a usable phone/Quest URL. Simulator data must remain visibly synthetic in review; never relabel it as real movement.

### Device source check during exchange

`POST /api/v1/devices/pair` accepts optional `expected_source` (`phone`, `quest`, or `simulator`). Phone and headset clients should set it to their source. A mismatch returns 422 without consuming the code. Successful exchange also returns `source` alongside the device ID, session ID and token.


## Combined mode and room setup

| Mode | Authoritative counter | Phone observation | Quest observation | Audio / primary controls |
|---|---|---|---|---|
| `phone` | Backend, phone stream | Projected 2D elbow angle | Optional separate observation | Phone |
| `quest` | Backend, Quest stream | Not required | Hand-to-target distance in meters | Quest |
| `combined` | Backend, Quest stream | Projected 2D right shoulder–hip tilt | Hand-to-target distance in meters | Quest |

Create combined sessions with `mode:"combined"`. They begin paused. Pair the phone first and start its camera **before putting the headset on**. The first paired phone supplies setup readiness; another phone cannot take that role over. Use a stationary, level, side-on phone with the right shoulder and hip visible. The backend requires at least `setup_hold_ms` of consecutive, recent, valid torso observations (default one second). Hidden/inferred joints, sequence gaps, stale capture and timestamp reversals reset readiness. Resume requires the latest observation to be no older than `gap_ms + 500` milliseconds after clock-offset correction. Pair Quest, keep the phone recording and visible, then send `session.resume` from Quest. A phone device token cannot resume a headset session. An authenticated browser can provide emergency controls.

`session.config.config` now includes `counter_stream`, `audio_owner`, `control_owner`, `capture_hz:10`, `batch_interval_ms:250`, `seated_only:true`, and `passthrough_required`. Implement headset **start/resume, pause, finish and mute** controls. Bind the first three to the existing `session.*` messages and mute locally. Stop the ghost animation when authoritative state is paused/complete. Use the immutable reach/return distances and `hold_ms` for ghost guidance; there is no metronome or automatic tempo claim. Show phone tracking coverage and review flags separately from Quest hand tracking. Never increment the displayed authoritative count from a local Unity event.

The phone is silent in Quest and combined modes, including tracking-loss cues. The headset is the only audio source. Pause from the headset before finishing and allow outstanding frame acknowledgements to drain. Completing a session rejects subsequent frames; an interrupted phone may have unsaved samples and must show that limitation. The browser remains available for emergency pause/finish and post-session check-in after removing the headset. Phone capture continues during a combined-mode pause to re-establish visibility; it never produces repetitions. A paused sample is labeled as paused in replay.

For trunk observation, the backend computes the unsigned angle between the right hip-to-shoulder vector and **image vertical**, correcting x by image aspect ratio. Only measured, visible shoulder/hip coordinates are used. A default 15-degree review threshold is a demonstration setting. The value is not baseline-calibrated flexion, not a physical 3D angle, and not evidence of clinical compensation by itself; a tilted camera changes the result. Phone and Quest clocks, coordinates, measurements and replay tracks remain distinct. Reports retain observed and flagged sample counts; these are not duration percentages. Frames identify `measurement_kind:"projected_2d_trunk_lean_degrees"` and `trunk_review`.

No new ping or acknowledgement type is necessary: `GET /time` supplies the clock estimate and `session.state.payload.ack_id` acknowledges commands/frames after commit. An idle socket now receives state changes from other devices within a nominal 500 ms polling interval; these unsolicited updates use an empty `ack_id`. They are state notifications, not acknowledgements of pending frames. Network and database latency add to that interval.

Synthetic combined tests use `simulator_phone` and `simulator_quest`, only on `is_synthetic:true` sessions. They cannot pair with a real session. Run `backend/.venv/bin/python scripts/verify_combined.py` to exercise HTTPS/WSS, both streams, setup gating, headset commands and separate replay tracks. This is not a physical headset acceptance test.

## Browser alternative and attempt cues

The `/quest` WebXR client now implements a browser alternative to the teammate-owned Unity app; see [Quest Browser setup](quest-browser.md). Unity clients can continue using the same REST/WSS interface. `exercise.feedback` may additionally carry `cue_id:"adjust"` and `attempt_id` for an observed return without holding the configured target. `session.state` can include `attempt`, `last_attempt` and attempt outcome counts. Existing clients should tolerate these additive fields; use the regenerated schema. The server still owns repetitions.
