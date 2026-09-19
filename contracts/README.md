# Integration artifacts

- `openapi.json`: FastAPI's exported REST specification. Regenerate after API changes; runtime `/api/openapi.json` is authoritative.
- `websocket.v1.schema.json`: JSON Schema 2020-12, a discriminated union of all seven client and five server message types.
- `websocket.v1.examples.json`: labeled examples covering every message type, valid Quest/phone frames and tracking loss. Values are illustrative synthetic coordinates, not observations.

From the repository root:

```sh
backend/.venv/bin/python scripts/export_openapi.py
backend/.venv/bin/python scripts/export_ws_schema.py
uv run --with jsonschema scripts/validate_contract_examples.py
```

The WebSocket generator reuses the backend's Pydantic frame and exercise configuration definitions and defines message envelopes explicitly. Keep server response shapes synchronized when changing the socket router. The version must change for incompatible wire changes. JSON Schema cannot express exercise state transitions, authenticated session membership, sequence deduplication, timestamps in relation to prior frames, or source authority; backend tests verify those semantics.

REST overview (all paths below `/api/v1`):

| Operation | Method/path | Credential |
|---|---|---|
| Sign in | `POST /auth/login` | Credentials in body |
| Current identity | `GET /auth/me` | User bearer |
| Server clock | `GET /time` | See OpenAPI |
| Authorized patients | `GET /patients` | User bearer |
| Patient | `GET /patients/{id}` | Authorized user bearer |
| Catalog | `GET /exercises` | User bearer |
| Assigned plan | `GET /patients/{id}/assignments` | Authorized user bearer |
| Assign exercise | `POST /assignments` | Authorized therapist bearer |
| Create session | `POST /sessions` | Authorized user bearer |
| Sessions for patient | `GET /patients/{id}/sessions` | Authorized user bearer |
| Session | `GET /sessions/{id}` | Authorized user or session device |
| Issue pairing code | `POST /sessions/{id}/pairing` | Authorized user bearer |
| Exchange code | `POST /devices/pair` | Secret unexpired pairing code |
| Device status / clock offset | `POST /sessions/{id}/device-status` | Session device bearer |
| Ingest batch | `POST /sessions/{id}/movement` | Session device bearer |
| Pause/resume/complete | `POST /sessions/{id}/{pause,resume,complete}` | Authorized user or session device |
| Patient check-in | `POST /sessions/{id}/checkin` | Assigned patient bearer |
| Replay | `GET /sessions/{id}/replay` | Authorized user bearer |
| Saved report | `GET /sessions/{id}/report` | Authorized user bearer |
| Approved speech cue | `GET /speech/{cue}` | User or device bearer |

See [Unity interface](../docs/unity-interface.md) for coordinate conventions, time, acknowledgement and reconnect behavior.
