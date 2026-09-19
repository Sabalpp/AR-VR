# Laptop services, real phone and Quest

All devices use one public HTTPS origin. Caddy forwards `/api/*` (including WebSocket upgrades) to FastAPI and everything else to Next.js. Device URLs never contain laptop `localhost`; the loopback listener is only the tunnel's local upstream.

1. Install Docker with Compose and an HTTPS tunnel client (for example Cloudflare Tunnel or ngrok).
2. Copy `.env.example` to `.env`. Set a new database password, a private `DEMO_PASSWORD`, and at least 32 random characters for `JWT_SECRET`. Use a URI-safe database password in this Compose setup, or percent-encode it in a custom `DATABASE_URL` deployment.
3. Start a tunnel to `http://127.0.0.1:8080`. For an installed Cloudflare client: `cloudflared tunnel --url http://127.0.0.1:8080`. It prints a public HTTPS origin. A named tunnel gives a stable origin; a quick tunnel changes when restarted.
4. Put that exact origin in `.env` as `PUBLIC_ORIGIN=https://...` (no trailing slash). Run `docker compose up --build -d`.
5. Open the **public HTTPS URL** on the laptop and phone. API requests are relative to that origin; WebSockets use the same hostname with `wss:`. The phone must grant camera permission. Mobile Safari/Chrome require a secure context for camera access.
6. If the tunnel origin changes, update `.env` and recreate backend: `docker compose up -d --force-recreate backend`. Reopen the new origin on devices.

Demo accounts are fictional and documented in README. Seed credentials are for a hackathon demo. This application has no public registration or password-reset workflow; do not place real patient records in this development instance.

Use `docker compose logs backend` for migration/API errors and `docker compose logs gateway` for routing problems. `docker compose restart backend` restarts application processing while retaining the PostgreSQL volume. `docker compose down` preserves data; adding `-v` deletes it and must not be used for the persistence acceptance test.

Browser camera troubleshooting: confirm HTTPS is trusted, allow site camera permission, close another app holding the camera, and keep the page foregrounded. Audio unlock is a separate explicit tap. Backgrounding or camera interruptions pause measurement. Re-enter setup and resume deliberately after restoring visibility. CDN access is needed for the browser MediaPipe model/WASM download unless those assets are self-hosted.

Public TLS termination and WSS upgrade support must be verified on the selected tunnel with the actual phone; container health and laptop-only requests do not prove that flow works. The acceptance checklist is in `docs/verification.md`.

## Verified container smoke test

On 2026-09-19, the complete Docker stack built and started in an isolated `arvr-smoke` Compose project using a private temporary environment file (`ENV_FILE` overrides the default `.env`). Python and Node images built successfully, Next.js production compilation and type checking passed, and PostgreSQL's health check passed.

Through the loopback Caddy gateway, `/`, `/api/v1/time`, `/api/docs`, and `/api/openapi.json` each returned HTTP 200. Fictional patient sign-in, session creation, pairing and WebSocket upgrades worked through the gateway. The labeled simulator completed one cycle in synthetic session `07c8d934-e37e-438f-a7ae-43866bf33a9f`. After backend container recreation, the session still had 18 stored frames and one completed repetition. Startup uses the dependencies already installed in the image, without downloading development packages.

This verifies the container build, migration/seed startup, internal routing, WebSocket upgrade and database persistence. It does **not** verify public HTTPS/WSS, real phone camera capture, actual Quest hardware or credentialed sponsor calls.
