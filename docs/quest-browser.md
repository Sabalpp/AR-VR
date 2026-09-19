# Quest 3 browser client and correction demo

The repository now includes a WebXR client at `/quest`. A Unity build is not required for this path. It is a **prototype ready for physical-device acceptance**, not a hardware-verified Quest release. Desktop checks and synthetic WebSocket streams do not establish real Quest wrist accuracy, readable headset panels, pinch usability, audio audibility or passthrough behavior.

## Connect a Quest 3

1. Keep the laptop, Docker project `arvr-tiger`, Tiger Data connection and HTTPS tunnel running. Use the actual public origin from private `.env`. The current quick tunnel is temporary.
2. On a phone/laptop, sign in as the fictional patient and select **Quest only** or **Phone + Quest** before creating a new session. For combined mode, allow the phone camera and finish the shoulder/hip visibility check first. Keep that phone stationary and its page visible.
3. Request a headset pairing code. In **Meta Quest Browser**, open the same public origin with `/quest` appended. Enable hand tracking and permit the browser's spatial tracking access. Enter the code within five minutes. No patient password is needed in the headset; the single-use code yields a session-scoped device token.
4. Stay seated with a clear reach area. Select **Enter passthrough**. The app requests `immersive-ar`, `local-floor` and `hand-tracking`; it does not silently fall back to opaque VR or controller-based wrist measurements.
5. Point and pinch with the **left hand** to select the in-headset buttons. Select **Start / resume**. The right wrist is the measured joint. Begin outside the amber return shell, move into the green target, hold for the saved duration, then return outside the amber shell and hold again. Default target radius is 0.12 m, return distance 0.30 m and hold 300 ms; the session's immutable configuration is authoritative. Do not strain to reach an uncomfortable target.
6. Use in-headset **Pause**, **Start / resume**, **Finish**, **Mute / unmute**, **Reconnect** or **Exit**. Finish waits for the outstanding frame acknowledgement, saves the session and exits passthrough. Remove the headset and submit the check-in on the phone. A Quest-only browser view also offers emergency pause/finish.
7. Sign in as therapist and open the session. Choose a missed or completed attempt under **Which attempts need a closer look?** to seek to its exact recorded start on the correct device stream.

## What is actually measured

The client obtains the right-hand `wrist` joint from `XRFrame.getJointPose`. Missing or emulated joint poses produce an explicit invalid frame with no joint coordinates. It never substitutes controller, head, target or ghost positions. The wire `visibility:1` is a binary pose-availability flag because this WebXR API does not supply a clinical accuracy score or MediaPipe-style confidence.

At first XR pose, the client establishes a stable floor origin directly beneath the seated viewer, aligned to their initial heading. Target rendering and sampled wrist positions use the same offset reference space. The right-handed WebXR `-Z` forward axis is converted to the existing Unity-style `+Z` forward wire convention by negating z; x and y are preserved. The saved target defaults to 0.5 m forward and 1 m above the floor. No phone/headset coordinate fusion or cross-device calibration is implied.

A reference-space reset stops capture and requests pause. Ending passthrough cannot be followed by a new tracking origin in the same browser capture: finish the old session and create a new one. Reconnection within the same still-open XR origin reuses the device token, obtains the saved sequence, pauses and requires deliberate resume. There is at most one frame awaiting acknowledgement, with a maximum target rate of 10 Hz. Network latency can reduce that rate. Timed-out/unacknowledged intervals are not filled with generated motion.

The in-headset green sphere is a spatial target; the amber shell marks return distance. It is not a full-body avatar or personalized therapeutic ghost. Whether this makes the task clearer than phone-only instructions requires an actual comparison with participants.

## Inspectable correction rule

An attempt begins after an observed held return when the authoritative wrist leaves the return zone. A held target followed by held return produces a completed repetition. Returning and holding without first holding the target produces `target_not_held`, **not** a repetition. Tracking loss, sequence gaps and capture-time gaps cannot create a success or a missed-target assertion; observed interrupted attempts are labeled separately. Pause/resume discards the partial attempt rather than joining motion across it. An unfinished attempt at session end is not classified as a missed target.

Each classified attempt is stored alongside its source frame in the existing movement chunk, with a stable device/sequence ID, start/end sequence and timestamps, best observed measurement, threshold and outcome. Replay buttons seek to those source samples. Reports retain the same attempt evidence; Gemini may select the corresponding allowed fact code but cannot write new numerical claims.

A missed-target event emits `exercise.feedback` with `cue_id:"adjust"` and `attempt_id`. The headset immediately displays the cue and requests approved ElevenLabs speech. Voice is optional, rate-spaced and can be muted; slow/failed audio does not block tracking. If the attempt is superseded before an audio response arrives, the obsolete correction is discarded. Audio playback is not presumed merely because the server generated MP3 bytes. Phone voice remains disabled in combined mode.

## Evidence and remaining gate

- `backend/tests/test_attempts.py` covers miss → corrected rep, deduplication, tracking interruption and a cue carrying the replay attempt ID.
- `scripts/unity_simulator.py --miss-first --repetitions 1 ...` verifies the server path with labeled synthetic coordinates over HTTPS/WSS. It does **not** drive the WebXR browser renderer or prove physical tracking.
- `scripts/quest_browser_smoke.mjs` checks unsupported-browser handling and seeks the two recorded attempts in the real clinician UI.
- [Verification report](verification.md) records results. Physical Quest checks remain: passthrough permissions, hand pose availability, target placement, panel/pinch usability, controls, clock/gaps, headset removal/recentering, loss/reconnect, audible cues, and manual review of actual repetitions.

Official platform references: [Meta WebXR hands](https://developers.meta.com/horizon/documentation/web/webxr-hands/), [Meta browser passthrough](https://developers.meta.com/horizon/documentation/web/webxr-mixed-reality/), and [XRFrame.getJointPose](https://developer.mozilla.org/en-US/docs/Web/API/XRFrame/getJointPose).
