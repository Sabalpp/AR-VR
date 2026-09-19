# Demo operations and remaining acceptance

The current working tree is `/Users/sabal/AR-VR`. The app runs in Docker project `arvr-tiger` against Tiger Data, behind `127.0.0.1:8081`. Both browser views, REST and WebSockets use the same public HTTPS origin in private `.env`. Keep the laptop awake, Docker running and the Cloudflare tunnel process alive.

The current quick tunnel is temporary. It does **not** satisfy the stable-domain requirement. For the venue, configure a named Cloudflare tunnel on a domain the team controls, set its upstream to `http://127.0.0.1:8081`, put that exact origin in `.env`, and recreate the backend:

```sh
docker compose -p arvr-tiger up -d --no-deps --force-recreate backend
```

Give that same origin to the Unity client. No owned domain or named-tunnel credentials have been configured in this repository. A hostname cannot be made permanent merely by changing `PUBLIC_ORIGIN`.

## Before the event

1. Use the private `DEMO_PASSWORD` for `therapist@demo.local` and `patient@demo.local`. Do not reset `.env` from the example.
2. Verify the physical phone over HTTPS: camera permission, model loading, visible joints, tracking loss, pause/resume, backgrounding and reconnection. The lite MediaPipe model is already used. Wake lock is requested; if unsupported or denied, the phone displays a manual auto-lock instruction. No camera video is uploaded.
3. For combined mode, finish phone setup before donning Quest. Remain seated, clear the reach area and enable passthrough. Use the new `/quest` browser client with start/resume, pause, finish and mute controls, or a compatible teammate Unity app. See [Quest Browser setup](quest-browser.md). The phone stays silent and records its separate trunk stream. Headset UI and physical hand tracking have **not** been tested here.
4. Capture a **real** short session before the event with the participants' agreement. Complete it, add a check-in, open the therapist replay and record the session ID and phone/headset details. Restart the backend and reopen it. Label it “Previously recorded real session” when presenting. There is no verified real recording in this handoff; existing movement verification records are visibly synthetic.
5. Save an offline screen recording of that real replay and report before the event. If internet fails, show that recording with its date and provenance. Do not call a simulator recording a patient capture.
6. Rehearse a phone-hotspot fallback: connect the laptop and headset, verify internet access, reopen the same named HTTPS origin and check WSS. If the capture phone cannot reliably provide both hotspot and camera, use a second phone for the hotspot. Test this with the actual hardware; it is not verified by laptop HTTP checks.

## Verified versus pending

Backend tests, public HTTPS browser workflows, hosted synthetic recording, restart persistence, the synthetic combined WSS flow and live Gemini/ElevenLabs calls have executable evidence in [verification.md](verification.md). The simulator is an explicitly labeled backup for a **technical protocol demonstration**, not the requested real-session backup.

Still pending: physical phone/Quest acceptance (including browser in-headset UI), any teammate Unity integration, named public domain, a previously recorded real backup, and the exact Impiricus challenge brief. Presage remains disabled. Tiger Data is actively used as PostgreSQL; hypertable/continuous-aggregate conversion has not been implemented. That conversion requires a deliberate migration because the current chunk uniqueness keys do not include a partition time column.

Gemini and speech are cuttable: the deterministic report, replay and authoritative counter remain available when providers fail. Gemini selects validated fact codes; it does not author numerical clinical claims. The current model was checked against [Google's model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash). The selected ElevenLabs voice was obtained from the account's [voice list API](https://elevenlabs.io/docs/api-reference/voices/search) and produced MP3 output.

Gemini 3.6 Flash uses minimal thinking for bounded fact ordering, following [Google’s thinking configuration](https://ai.google.dev/gemini-api/docs/generate-content/thinking). This reduces unnecessary reasoning latency but does not guarantee every provider request succeeds.
