# API × Model Matrix

Every backend endpoint that produces or consumes M1–M5 predictions.

## Prediction endpoints (`backend/app/api/v1/predict.py`, prefix `/predict`)
| Endpoint | Method | Model | Service | Notes |
|---|---|---|---|---|
| `/predict/m1/{student_id}` | GET | M1 v1 (legacy) | `PredictionContractService.predict_m1` | Unified contract; READY; ValueErr→404 |
| `/predict/m1v2/{student_id}` | GET | M1 V2 | `M1V2PredictionService.predict` | NO_DATA→200; FileNotFound→503 |
| `/predict/m1v3/{student_id}` | GET | M1 V3 (synthetic) | `M1V3PredictionService.predict` | same semantics as V2 |
| `/predict/m2/{student_id}` | GET | M2 v1 (legacy) | `PredictionContractService.predict_m2` | READY; legacy |
| `/predict/m2v2/{student_id}` | GET | M2 V2 | `M2V2PredictionService.predict` | ValueErr→404; FileNotFound→503 |
| `/predict/m3/{student_id}` | GET | M3 v1 | `PredictionContractService.predict_m3` | **BLOCKED**; route 403s non-BLOCKED |
| `/predict/m3v2/{student_id}` | GET | M3 V2 | `M3V2PredictionService.predict` | probability + threshold + top signals |
| `/predict/m4/{student_id}` | GET | M4 (rule-based) | `PredictionService.predict_m4_for_student` | returns `PredictionResult` |
| `/predict/insights/{student_id}` | GET | M1–M4 bundle | `PredictionInsightsService.get_student_insights` | per-model degrade; ML-08 explanations |
| `/predict/persist/{type}/{student_id}` | POST | m1/m2/m3/m4 | `PredictionGenerationService.generate_and_persist` | append-only persistence; ML-07 |
| `/predict/persisted/latest/{type}/{student_id}` | GET | m1/m2/m3/m4 | `PredictionGenerationService.get_latest` | latest by generated_at DESC |
| `/predict/persisted/history/{student_id}` | GET | m1/m2/m3/m4 | `PredictionGenerationService.get_history` | paginated newest-first |

All routes gate via `authorize_prediction_access` (Student own-id / Faculty scope / Admin any).

## Non-predict endpoints that consume models
| Endpoint | Model consumed |
|---|---|
| `GET /students/me/career/readiness` (`student.py`) | M4 (CareerReadinessResponse) |
| `GET /students/me/career/guidance` (`student.py`) | M5 (coach), M4-as-evidence |
| `GET /faculty/students/{student_id}/ml-insights` (`faculty.py:310`) | M1–M4 via `PredictionInsightsService` (scoped) |
| `GET /admin/ml-intelligence` (`admin.py:286`) | M1–M4 aggregates via `AdminMLService` |
| `POST /admin/ml-intelligence/generate` (`admin.py:309`) | M1–M4 batch generation (job) |
| `GET /admin/ml-intelligence/generate/status/{job_id}` (`admin.py:355`) | batch status |
| `GET /admin/ml-feedback` (`admin.py:375`) | feedback health (prediction_feedback) |
| `POST /chat` (`chat.py:47`) | M1–M4 via tools (persisted rows) |
| `POST /students/.../feedback` (faculty.py) | prediction feedback writes (additive) |

## Notes for NEW Clean M1_v3
- A new endpoint (`/predict/m1v3clean/{student_id}` or replacement) is the only API-layer change needed; the persisted-latest/history endpoints are type-keyed and version-agnostic (`prediction_type='m1'`).
- Any new endpoint MUST run through `authorize_prediction_access` and return 503 on missing artifact (matching V2/V3 contract) to keep the student page's `NO_DATA` handling intact.