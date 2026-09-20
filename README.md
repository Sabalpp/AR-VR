# Meta Care

A VR-based **musculoskeletal screening device** for remote/rural care. A patient
wears a Meta Quest 3, describes their pain by voice, is guided through movement
tests, and receives an AI screening suggestion with confidence scores — while
the recording, 3D movement replay, and objective metrics are sent to a remote
physician for verification through the **doctor portal**.

> Clinical decision support only. Every AI suggestion requires physician review.

## Device flow

```
wear headset
  → device speaks "explain your pain"          (ElevenLabs TTS)
  → patient speaks                              (Gemini transcription / Live)
  → triage complaint → suspected conditions     (Gemini, grounded in a curated catalogue)
  → prescribe a discriminating test battery     (arpt/medical/mapping.py)
  → VR shows green-path guide, tracks movement  (arpt/core/motion_state.py)
      red = not moving · yellow = in motion · green = target reached
  → form gate fails → redo loop
  → record .skel, render 3D character replay     (skeleton_video.py)
  → screen: Gemini (grounded) + TensorFlow model, confidence scores
  → build doctor-portal report                   (arpt/portal/)
  → physician reviews & verifies                 (React dashboard)
```

## Architecture

```
arpt/                     Python package (the shipped backend)
  core/     skel parser · kinematics · motion-state / form-guide engine
  medical/  condition catalogue · movement tests · condition↔test mapping
  ml/       dataset (+augment/synthetic) · TF model · train · infer
  ai/       Gemini triage+diagnosis (catalogue-grounded) · voice (11Labs/Live) · config
  portal/   FastAPI server (API + serves the built SPA) · static fallback UI
  session.py  end-to-end orchestrator

dashboard/                Meta Care doctor dashboard (React + CoreUI + Vite)
  src/api/arpt.js          API client
  src/views/arpt/          Overview · Queue · PatientDetail
  build/                   production bundle (served by FastAPI)

tests/                     pytest suite for the arpt package + API security
recordings/                sample .skel recordings + labels.json
models/                    trained classifier artifacts (git-ignored)
reports/                   runtime patient reports (git-ignored)
```

## Requirements

- **Python 3.12** (TensorFlow has no wheels for 3.13/3.14)
- **Node 18+** (built with Node 26)

## Setup

```bash
# 1. Backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Secrets (optional — portal works without them; AI screening needs Gemini)
cp .env.example .env      # then fill in GEMINI_API_KEY (and ELEVENLABS_API_KEY)

# 3. Frontend
cd dashboard && npm install && npm run build && cd ..
```

## Run

### Production (single service)
FastAPI serves both the API and the built React dashboard on one port:

```bash
venv/bin/uvicorn arpt.portal.server:app --port 8000
# open http://localhost:8000
```

### Development (hot reload)
Run the API and the Vite dev server separately; Vite proxies `/api` → :8000.

```bash
venv/bin/uvicorn arpt.portal.server:app --reload --port 8000   # terminal 1
cd dashboard && npm start                                       # terminal 2 → :3000
```

### Other commands
```bash
# Seed demo reports (no Gemini calls; attaches per-patient replay video)
venv/bin/python seed_demo.py

# Full patient session (needs GEMINI_API_KEY) → writes reports/<id>.json
venv/bin/python -m arpt.session recordings/rec_20260919_164205.skel \
    --pain "left knee unstable on stairs, locks up" --patient patient_014

# Render a 3D character replay video
venv/bin/python skeleton_video.py recordings/rec_20260919_164205.skel

# Train the condition classifier
venv/bin/python -m arpt.ml.train --synthetic                    # validate pipeline
venv/bin/python -m arpt.ml.train --manifest recordings/labels.json
```

## Verify

```bash
venv/bin/python -m pytest tests/ test_skeleton_video.py -q      # backend + API
cd dashboard && npx eslint && npm run build                     # frontend
curl -s http://localhost:8000/health                            # liveness
```

## Configuration

| Variable | Required | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | for AI screening | Gemini triage & diagnosis |
| `ELEVENLABS_API_KEY` | optional | device speech-out (TTS) |
| `METACARE_CORS_ORIGINS` | prod only | allowed frontend origins if served cross-origin |
| `GEMINI_MODEL` / `GEMINI_LIVE_MODEL` | optional | model overrides |

Secrets are read from the environment (or a local `.env`). None are hard-coded.
Calls that need a missing key raise a clear, actionable error.

## Known limitations / next steps

- **ML model** is a real temporal CNN+GRU multi-label classifier, but only 3
  sample recordings exist, so it memorizes. It becomes meaningful once a labeled
  corpus is collected. `recordings/labels.json` labels are illustrative placeholders.
- Gemini free tier is 20 requests/day; the portal itself needs no live Gemini
  calls (reports are precomputed).
- The **VR/Unity front-end** (Quest app) consumes `arpt/core/motion_state.py`
  green-path targets and `arpt/medical/tests.py` phase definitions — not in this repo.
- Auth: the portal has **no login yet** — add authentication before exposing PHI
  publicly. Reports are stored as flat JSON (fine for a pilot, not multi-tenant).
- Sponsor integrations (Impiricus, Tiger data) not yet wired.
