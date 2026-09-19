# Healthier architectural study

Reference: [scrappydevs/healthier at 8dbc1ac6b3469f30f44b36b1e6755aa3125be1fa](https://github.com/scrappydevs/healthier/tree/8dbc1ac6b3469f30f44b36b1e6755aa3125be1fa). Inspected the pinned checkout, not the moving default branch. This project contains fresh implementation, not a port.

| Inspected reference | Useful architectural idea | Our implementation decision |
|---|---|---|
| `frontend/lib/api.ts` | Central typed request boundary, timeouts, patient/exercise DTOs | Keep browser requests behind a typed API module; same-origin URLs; authenticated identity. Never distribute a laptop localhost URL to devices. |
| `frontend/app/(app)/dashboard/patients/[id]/page.tsx` | Route composes patient summary and focused sections with loading/error states | Compose patient overview, assigned plan, and session review. Do not import food/medication views or classify clinical risk from arbitrary adherence cutoffs. |
| `frontend/components/patient/ExerciseSection.tsx` | Date-grouped exercise review and asynchronous pose-analysis review | Link session review to an assignment ID and saved measurements. At the pinned commit this component is primarily review; prescription operations live in the API. |
| `backend/app/api/v1.py` | Catalog, prescriptions, adherence, background analysis and cached results | Separate API routers, repositories, analysis, providers and reporting. Persist metrics before optional narration. |
| `backend/app/services/pose_analysis.py` | Named MediaPipe landmarks and joint-angle triplets, measurements before prose | Use named joints, visibility checks and aspect-corrected projected 2D elbow angles. Do not inherit its `difference < 15` universal symmetry rule or ideal ranges. |
| `nexhacks-ios/nexhacks-ios/Services/ExerciseAnalysisService.swift` | Explicit connect/start/stop lifecycle, feedback state, three-second cooldown and duplicate speech suppression | Reimplement lifecycle for a mobile browser; explicit audio unlock, visibility/camera interruption handling and bounded sending. Do not port Swift or default `formScore = 7`. |
| `overshoot-service/src/index.js` | Bidirectional start/frame/analysis/stop/summary flow and upgrade routing | Versioned authenticated messages with explicit acknowledgements and deterministic server processing. No image-to-LLM repetition counting. |
| `supabase/migrations/` | User/patient foreign keys, catalog and prescription relationships, timestamped records | Fresh incremental Alembic schema; explicit therapist access and assignment/session relationships; no copied DROP/recreate sequence. |

Confirmed pitfalls: `overshoot-service/src/overshoot.js:analyzeExerciseFrame` returns `mockAnalysis`, which uses `Math.random()` for exercise, repetitions, feedback and scores. None becomes real measurement here. The reference's `/users/me` selects the first clinician rather than authenticating a principal. Its exercise adherence code matches prescription names against exercise labels; ours uses immutable assignment foreign keys. The reference angle calculation directly uses normalized x/y, distorting non-square images; ours corrects aspect ratio before projected angle calculation.

Repository baseline was an empty Git repository with no existing Node backend or Unity files to migrate. FastAPI therefore introduces no replacement cost. Teammates' future Unity work remains separate from `frontend/`, `backend/`, `contracts/`, and `docs/`.
