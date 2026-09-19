# Reach — physical therapy session platform

Therapist dashboard, phone-browser seated-reach capture, FastAPI/PostgreSQL backend, replay and a versioned Unity interface. Fresh code inspired by the architectural workflows of [Healthier](https://github.com/scrappydevs/healthier/tree/8dbc1ac6b3469f30f44b36b1e6755aa3125be1fa). Unity/Meta Quest application work belongs to the headset team.

**Completion status:** consult [verification evidence](docs/verification.md). Automated or synthetic results do not establish a real phone capture or an actual Quest connection. Both require their own acceptance run.

## Run the demo

```sh
cp .env.example .env
# Edit .env: PUBLIC_ORIGIN, JWT_SECRET, database password and DEMO_PASSWORD.
docker compose up --build -d
```

The gateway listens at `http://127.0.0.1:8080` on the laptop. For camera capture on a phone, expose that listener through an HTTPS tunnel and use its public origin on **all devices**. See [exact HTTPS instructions](docs/local-https.md). Containers retain PostgreSQL data in a named volume. Backend startup runs incremental migrations and fictional demo seeding.

Fictional accounts: `therapist@demo.local` and `patient@demo.local`. Use the `DEMO_PASSWORD` configured before initial seeding; never publish these credentials. For local-only tests without an override, the seeded defaults are `DemoTherapist123!` and `DemoPatient123!`. No real patient or real completed movement session is seeded.

Open the therapist dashboard, choose the fictional patient, and assign seated reach. Open the patient account on a phone to see the assignment. Start camera setup, grant permission, enable audio if desired and perform the configured movement. Finish and submit the separate check-in. Review its saved tracking, repetitions, replay and report on the dashboard. Restart backend with `docker compose restart backend` and reopen the same session to perform the durability acceptance check.

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
