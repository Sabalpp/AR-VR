# Reach — physical therapy session platform

Therapist dashboard, phone-browser seated-reach capture, FastAPI/PostgreSQL backend, replay and a versioned Unity interface. Fresh code inspired by the architectural workflows of [Healthier](https://github.com/scrappydevs/healthier/tree/8dbc1ac6b3469f30f44b36b1e6755aa3125be1fa). Unity/Meta Quest application work belongs to the headset team.

**Completion status:** consult [verification evidence](docs/verification.md). Automated or synthetic results do not establish a real phone capture or an actual Quest connection. Both require their own acceptance run.

## Hosting: one laptop, one website, two views

**The therapist dashboard and patient phone app do not need separate hosting.** They are two routes in the same Next.js website, served by your laptop. Both use the same FastAPI backend and PostgreSQL database. The phone runs its browser and camera; it does not run a separate server.

| What to open | Address | Where |
|---|---|---|
| Sign in | `https://YOUR-TUNNEL-HOST/` | Laptop or phone |
| Therapist dashboard | `https://YOUR-TUNNEL-HOST/dashboard` | Laptop browser, signed in as therapist |
| Patient app | `https://YOUR-TUNNEL-HOST/patient` | Phone browser, signed in as patient |
| Local website preview | `http://127.0.0.1:8080` | Laptop only |
| API documentation | `https://YOUR-TUNNEL-HOST/api/docs` | Laptop browser |
| Quest WebSocket endpoint | `wss://YOUR-TUNNEL-HOST/api/v1/ws/SESSION_ID` | Unity client, with the documented device-token handshake |

`YOUR-TUNNEL-HOST` is a placeholder. Replace it with the actual hostname printed by the tunnel command below. No live public URL is assigned by this README. Open the sign-in page first; your account determines which view opens.

```mermaid
flowchart TD
    Therapist["Therapist: laptop browser /dashboard"] --> Public["Same public HTTPS hostname"]
    Patient["Patient: phone browser /patient"] --> Public
    Quest["Quest: WSS connection"] --> Public
    Public --> Tunnel["HTTPS tunnel running on your laptop"]
    Tunnel --> Gateway["Laptop gateway: 127.0.0.1:8080"]
    Gateway --> Frontend["Next.js: dashboard + patient app"]
    Gateway --> Backend["FastAPI: /api/* and WebSockets"]
    Backend --> Database["PostgreSQL: saved sessions"]
```

### Which IP does my phone connect to?

**For this setup, send your phone the tunnel's public HTTPS link, not your laptop's raw IP address.** The tunnel forwards that link to `http://127.0.0.1:8080` on your laptop. On your phone, `localhost` and `127.0.0.1` mean the phone itself, not your computer.

Your laptop also has a network IP. On this Mac, you can inspect the address on `en0` with:

```sh
ipconfig getifaddr en0
```

If that prints nothing, check System Settings → Wi-Fi → Details → TCP/IP for the active connection. The address can change when you change networks, so do not hard-code it into the phone or Unity app.

The current Docker configuration binds port 8080 to **laptop loopback only** (`127.0.0.1:8080:8080`). Therefore `http://YOUR-LAPTOP-IP:8080` is not a working phone URL in this configuration. Also, a plain HTTP network-IP page does not meet browser camera secure-context requirements. Use the HTTPS tunnel for the camera demo. See [browser camera requirements](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia).

### Start it and connect your phone

You need Docker with Compose and the `cloudflared` tunnel client installed on your laptop. Cloudflare documents the temporary tunnel command in its [Quick Tunnels guide](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/).

1. Open a terminal in this repository and copy the environment template **once**:

   ```sh
   cd /path/to/AR-VR
   cp .env.example .env
   ```

   Edit `.env`: choose private values for `POSTGRES_PASSWORD`, `DEMO_PASSWORD`, and `JWT_SECRET` (at least 32 random characters). Keep an existing `.env` if you already configured one.

2. In a second laptop terminal, start the tunnel and leave it running:

   ```sh
   cloudflared tunnel --url http://127.0.0.1:8080
   ```

   It prints an address shaped like `https://YOUR-ASSIGNED-NAME.trycloudflare.com`. Copy the **actual printed address**. Until the Docker app starts, opening it may show an upstream connection error.

3. Set `.env` to that exact address, with no trailing slash:

   ```dotenv
   PUBLIC_ORIGIN=https://YOUR-ASSIGNED-NAME.trycloudflare.com
   ```

4. Back in the repository terminal, start the application:

   ```sh
   docker compose up --build -d
   docker compose ps
   ```

   This local-fallback command starts the website, backend, database and gateway. For hosted Tiger Data, use the command in the database section below. The backend runs migrations and seeds fictional accounts. PostgreSQL stores sessions in a persistent Docker volume.

5. On the **laptop**, open the printed HTTPS address, sign in as `therapist@demo.local` using your configured `DEMO_PASSWORD`, and assign an exercise. The dashboard is at `/dashboard`.

6. Send that **same HTTPS address** to your **phone**. Open it in Safari or Chrome, sign in as `patient@demo.local` using your configured `DEMO_PASSWORD`, and open `/patient`. Allow camera access when starting the exercise. No phone app installation or separate patient hosting is needed.

7. Keep Docker running, the tunnel terminal open, and the laptop awake and connected to the internet throughout the demo. The phone needs internet access; with this public tunnel it does not have to use the same Wi-Fi network as the laptop.

A temporary tunnel usually gets a new hostname when restarted. Update `PUBLIC_ORIGIN`, run `docker compose up -d --force-recreate backend`, and share the new link. Changing `PUBLIC_ORIGIN` alone does not create a tunnel or public hostname. See [additional HTTPS troubleshooting](docs/local-https.md).

### Accounts and saved sessions

The two accounts are fictional. Use the `DEMO_PASSWORD` configured **before initial seeding**. Changing that variable later does not change passwords for users already in the database. For local-only tests without an override, the seed defaults are `DemoTherapist123!` and `DemoPatient123!`; configure private credentials before sharing the tunnel. No real patient or completed movement session is seeded.

After the phone session, submit the check-in and review its tracking, repetitions, replay and report in the therapist dashboard. Verify durability with `docker compose restart backend`, then reopen the same session. This restarts the backend while preserving the database. Physical-phone and actual Quest acceptance remain pending until recorded in [verification evidence](docs/verification.md).

## Database: Tiger Data

**Tiger Data is the intended hosted database.** It provides PostgreSQL; the backend connects using your service's **database connection URL**, not a Tiger Data management API key. Get the URL from your service's connection details in the Tiger Data console ([connection instructions](https://docs.tigerdata.com/use-timescale/latest/integrations/find-connection-details/)).

Open your private configuration:

```sh
vim /Users/sabal/AR-VR/.env
```

Fill in the existing `DATABASE_URL` line with the actual service URL:

```dotenv
DATABASE_URL='postgresql://USER:URL_ENCODED_PASSWORD@HOST:PORT/DATABASE?sslmode=require'
```

Use the host, port, username, database name and TLS parameters supplied by Tiger Data. Preserve percent-encoding in the URL password. The backend automatically selects its installed psycopg driver. Keep this URL server-side in `.env`; never put it in a `NEXT_PUBLIC_` variable or the phone/Quest app.

With `DATABASE_URL` configured, start only the application services (the database is hosted remotely):

```sh
docker compose up --build -d --no-deps backend frontend gateway
```

Startup applies our migrations and fictional demo seed to that database, so use a dedicated hackathon database. The existing local Docker `db` and its volume are unchanged. Existing local records are not automatically copied to Tiger Data. Hosted connection/migrations remain unverified until real service credentials are configured and tested.

If `DATABASE_URL` is empty, the regular `docker compose up --build -d` command uses **local PostgreSQL as a development fallback**. `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` configure that local fallback; they are not your Tiger Data credentials. With Tiger Data, records live in the hosted service rather than the local Docker volume. Both web views still run on the laptop and use the same HTTPS tunnel.

## Repository

| Directory | Purpose |
|---|---|
| `frontend/` | Next.js App Router, React/TypeScript, Tailwind, Radix and Zustand; isolated browser MediaPipe and Three.js replay |
| `backend/` | FastAPI/Pydantic API and WebSockets, SQLAlchemy repositories/models, Alembic, deterministic movement analysis and optional providers |
| `contracts/` | Exported REST OpenAPI and discriminated WebSocket v1 JSON schema |
| `scripts/` | Synthetic Unity client, contract generation and verification utilities |
| `docs/` | [Engineering plan](docs/engineering-plan.md), [reference findings](docs/reference-findings.md), [Unity contract](docs/unity-interface.md), [sponsor boundaries](docs/sponsors.md), acceptance evidence |

Backend runtime OpenAPI is `/api/openapi.json` and interactive docs `/api/docs` (through the public gateway). Checked-in contracts make integration review possible without a running server. Generate frontend REST types using `npm run generate:api` in `frontend/` after exporting the backend OpenAPI.

## Local development and checks

Use Python 3.11+ and Node.js 22+. Backend dependencies and tests are described in `backend/pyproject.toml`; `uv sync --group dev` creates its environment. Set `DATABASE_URL` to a running PostgreSQL database and run `uv run alembic upgrade head`, `uv run python -m app.seed`, and `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000` from `backend/`. API/provider environment variables remain on the server.

From `frontend/`, run `npm ci` and `npm run dev`. `BACKEND_INTERNAL_URL` is the server-only reverse-proxy upstream, defaulting to the laptop backend during development. The Docker gateway routes WebSockets directly to the backend. Use the HTTPS tunnel/gateway setup for physical devices.

```sh
# From backend/
uv run pytest
# From frontend/
npm run typecheck
npm run build
# From repository root, using the backend environment
backend/.venv/bin/python scripts/export_ws_schema.py
```

The [Unity simulator](docs/unity-interface.md#synthetic-simulator) generates only labeled synthetic Quest-coordinate sessions. Configure its `SIMULATOR_PASSWORD` to match your seeded patient's password when overridden.

## Measurement and integration scope

Phone mode uses aspect-corrected **projected 2D elbow angle**. Quest mode uses hand-to-target distance in a stable Quest local origin, in meters. No phone depth is treated as calibrated distance; streams are not fused. Backend state machines own the repetition count, with held phases, hysteresis and invalid/gap/pause resets. Configuration is copied immutably into each session. Thresholds are demonstration targets, not clinical truths or form scores.

Gemini and ElevenLabs are optional server-side integrations. Missing keys or provider failure leave measurements and session review available. Impiricus is represented by the clinician review workflow, with no invented API integration. Presage stays disabled pending verified platform/access support. See [sponsor boundaries and official documentation](docs/sponsors.md).
