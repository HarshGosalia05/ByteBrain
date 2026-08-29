# READ-ONLY Backend Prediction API (Consuming the Unified Offline Inference Contract)

## 1. Objective

Prove the backend can serve predictions correctly by building a **read-only
prediction API** that consumes the unified offline inference contract
(`ml/src/features/v1_inference_contract.py`).

The API:
- accepts validated student data (read directly from the DB), calls the
  existing inference contract, and returns M1 and M2 predictions;
- exposes M3 as **BLOCKED**, not as an approved prediction;
- does **not** retrain models;
- does **not** write predictions back to the database (initially);
- does **not** duplicate feature engineering.

## 2. Design decisions (confirmed with owner)

1. **Refactor the existing `/predict` router** to consume the unified contract
   (rather than adding a parallel router), so M3 becomes BLOCKED on the live
   endpoints.
2. **Backend reads from DB** — endpoints take `student_id`; real student data is
   fetched via the existing authoritative read-only repositories and fed to the
   contract.
3. **Endpoints return the contract shape** — the readiness-aware
   `InferenceResult` JSON (with `readiness_status`, `prediction_available`,
   `reason`), so M3 naturally surfaces as `BLOCKED`. Legacy consumers
   (`/predict/insights`, `/predict/persist`, M4, frontend) remain untouched.

## 3. Files created / modified

| File | Change |
|---|---|
| `backend/app/services/prediction_contract_service.py` | **NEW.** Read-only service that fetches real DB data and calls the unified contract. |
| `backend/tests/test_prediction_contract_service.py` | **NEW.** Focused service + HTTP tests (real contract + real artifacts). |
| `backend/app/api/v1/predict.py` | **Modified.** `GET /predict/m1\|m2\|m3` rewired to the contract service; added `get_contract_prediction_service` DI. |
| `ml/tests/test_prediction_generation_api.py` | **Modified.** `TestExistingGETReadOnly` updated to the contract DI + response shape. |

## 4. New service responsibilities

`PredictionContractService(pool)` is read-only and orchestrates exactly:

```
real DB data (existing read-only fetch helpers)
  -> per-row feature dicts
  -> v1_inference_contract.predict_mX(row)   (the unified contract)
  -> readiness-aware InferenceResult JSON
```

- **M1** `predict_m1(student_id)` — one `InferenceResult` per subject
  enrollment; `READY`; each prediction clipped to `[0,70]`, 1 decimal.
- **M2** `predict_m2(student_id)` — uses the **latest completed semester**
  summary row; `READY`; `prediction` = `{next_semester_percentage,
  next_semester_sgpa}` (2 decimals).
- **M3** `predict_m3(student_id)` — same data path but returns a
  **BLOCKED** result: `readiness_status="BLOCKED"`, `prediction_available=False`,
  `prediction=None`, with the standardized blocked reason. No real at-risk
  prediction is ever exposed.

## 5. Reused modules (no duplication, no retraining)

- **Unified contract**: `ml.src.features.v1_inference_contract`
  (`predict_m1/m2/m3`, `get_readiness`, `InferenceResult.to_dict`).
- **Feature engineering**: NOT duplicated. The contract itself calls the
  existing `ml.src.features.prepare_m1/m2/m3_inference` (exact training-time
  encoding/order). The backend builds only the raw feature dicts from real data.
- **Model loading**: the contract uses `ml.src.registry.load_model` (authoritative,
  cached, read-only). Artifacts are never written or regenerated.
- **Data access**: the service reuses `ml.src.prediction_service._fetch_*`
  read-only helpers (`_fetch_student_performance`, `_fetch_subject_type`,
  `_fetch_student_profile`, `_fetch_student_semester_summary`). No new SQL.

## 6. Read-only guarantees

- **No DB writes**: the new service contains no `INSERT/UPDATE/DELETE` and no
  direct DB handle (`execute`/`fetch*`/`acquire`); it only calls the read-only
  fetch helpers. Nothing is persisted by `GET /predict/m1|m2|m3`.
- **No retraining**: artifact SHA-256 hashes are byte-identical after the step.
- **No feature-engineering duplication**: only the contract + existing
  `prepare_*_inference` encode/preprocess.
- The pre-existing opt-in `/predict/persist` flow is left as-is (unchanged);
  it is a separate caller-driven write path and was not touched by this step.

## 7. M3 blocked semantics

`GET /predict/m3/{student_id}` returns a 200 with:

```json
{
  "model_id": "m3",
  "readiness_status": "BLOCKED",
  "prediction_available": false,
  "prediction": null,
  "reason": "M3 validation gate is blocked ... No production prediction is available.",
  ...
}
```

No `is_at_risk_next_sem` value is returned. The service calls the contract with
`allow_offline_score=False` (default), so the offline model is never scored in
production serving either.

## 8. Tests

### New: `backend/tests/test_prediction_contract_service.py` (8 tests)
- Service-level vs the **real** contract + artifacts: M1 READY (per-subject,
  clipped `[0,70]`, 12 features), M2 READY (both targets, floats), M3 BLOCKED
  (no prediction), no-data -> `ValueError`.
- HTTP-level (`TestClient`): `GET /predict/m1|m2|m3` wired to the contract
  service; M3 confirmed BLOCKED with no real prediction.

### Updated: `ml/tests/test_prediction_generation_api.py`
- Read-only GET test now uses the contract DI dependency and asserts the
  contract response shape; verifies persistence is never invoked.

### Results
- Focused predict-related set (backend + ml): **96 passed, 0 failed**.
- Full `ml/tests` suite: **713 passed, 0 failed, 246 warnings** (unchanged
  baseline).
- Full `backend/tests` suite: **1203 passed** with my change. A pre-existing
  cluster of **85 failures in `test_analytics.py` / `test_analytics_service.py`**
  is present identically on the clean baseline (with my files stashed: 1195
  passed / 85 failed); it is caused by a test-ordering / async event-loop issue
  in the analytics tests, **unrelated to this change**. The delta vs baseline is
  exactly `+8` (my new passing tests) with **no new failures**.

## 9. Artifact integrity (no retraining)

Byte-identical before and after:
- M1 `m1_subject_endmarks.joblib` — `3404D29EE61C151C39B50CB9F00D9EE268B8CAF7B39F8BB24D01F17EBFC6431E`
- M2 `m2_next_semester_performance.joblib` — `6CAC9A884ABAEF16575D7B866405A726F751BEFC18359C3C599AFDB5E071C012`
- M3 `m3_next_semester_at_risk.joblib` — `99D845FE64A9002B7B1176975A0B41CF29F16A57D380993DA260E2557E2044A7`

## 10. Endpoint summary

| Endpoint | Readiness | Prediction | Notes |
|---|---|---|---|
| `GET /predict/m1/{student_id}` | `READY` | per-subject, `[0,70]` | real DB data, contract |
| `GET /predict/m2/{student_id}` | `READY` | pct + sgpa | real DB data, latest semester |
| `GET /predict/m3/{student_id}` | `BLOCKED` | `null` | never an approved prediction |
| `GET /predict/m4/{student_id}` | (legacy, unchanged) | rule-based | not in contract scope |
| `GET /predict/insights/{student_id}` | (legacy, unchanged) | bundle | unchanged |
| `/predict/persist/*` | (legacy, unchanged) | opt-in write | unchanged |

Auth (`authorize_prediction_access`) is unchanged and still enforced on every
route.

## 11. Limitations

- **Read-only only.** No predictions are written back to the DB initially.
- **M3 remains BLOCKED**; nothing here grants M3 production approval.
- The response shape for `GET /predict/m1|m2|m3` changed from the legacy
  `PredictionResult` list shape to the contract structured shape. Consumers of
  that legacy shape via these three endpoints must migrate; the insights, M4,
  persist, and frontend surfaces are unaffected.
- The pre-existing full-suite analytics test failures are present on the clean
  baseline and are out of scope for this task.

## 12. Exact next single step

**STOP.** Do not build further.

Proposed next **separate** milestone (not performed here):
> **PREDICTION WRITE-BACK / FEEDBACK LOOP** — add explicit, caller-driven
> persistence of contract predictions and a feedback loop, reusing the existing
> ML-06 `ml_predictions` design, only after the read-only API is accepted.

## Final verdict

```
READ_ONLY_PREDICTION_API_CONSUMES_UNIFIED_CONTRACT_READY
```
