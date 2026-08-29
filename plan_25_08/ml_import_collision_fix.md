# ML Import/Module Collision Fix Report

## 1. Problem

Two same-named `features` targets coexisted after V1 feature engineering:

- `ml/src/features.py` — pre-existing **module**: the M1/M2/M3/M4 feature-preparation layer (`FeatureContract`, `M1_CONTRACT`, `M2_CONTRACT`, `M3_CONTRACT`, `get_contract`, `_one_hot_encode`, `build_*`, `prepare_*`, `validate_raw_features`, ...).
- `ml/src/features/` — **package** created during V1 feature engineering (`v1_config`, `v1_dataset`, `v1_validation`, `v1_split*`, `v1_baseline_m3`).

Python resolves the **package** over the same-named module on `sys.path`. Existing imports of the module-level contracts — `from features import M1_CONTRACT, M3_CONTRACT` and `from ml.src.features import M3_CONTRACT, _one_hot_encode` — therefore failed at collection because the package `__init__.py` did not export those names.

Affected (previously failing at collection):
- `ml/tests/test_features.py`
- `ml/tests/test_inference.py`
- `ml/tests/test_retrain_m3.py`
- runtime imports in `ml/src/retrain_m3.py`, `ml/src/inference.py`, `ml/src/prediction_service.py`

## 2. Approach (smallest backward-compatible fix)

Per the guidance, **re-export the existing module-level contracts from the package `__init__.py`** — no redesign, no renamed files, no ETL, no feature/model changes.

The legacy `features.py` module is loaded under a private name (`_features_legacy`), registered in `sys.modules` before execution (required for the `FeatureContract` `@dataclass` to resolve), and its public module-level API is re-exported into the package namespace.

Result — all three import styles now coexist:
- `from features import M1_CONTRACT, M3_CONTRACT, _one_hot_encode, ...` ✓
- `from ml.src.features import M3_CONTRACT, _one_hot_encode` ✓
- `from features.v1_config import V1Config` (V1 package submodules) ✓

## 3. Behaviour preservation

- `M3_CONTRACT` returned by `from features import M3_CONTRACT` is the **same object** as `from ml.src.features import M3_CONTRACT` (identity checked — no duplicated/divergent contracts).
- `features.py` was not modified; it is loaded and re-exported verbatim.
- V1 feature definitions, model behaviour, encoding, and evaluation are untouched.

## 4. Files changed

| File | Change |
|------|--------|
| `ml/src/features/__init__.py` | MOD — load `features.py` under `_features_legacy` and re-export its public API; extend `__all__` |

Only one file changed.

## 5. Verification

### Previously-broken modules (now pass)

| Module | Tests |
|--------|-------|
| `test_features.py` | 38 passed |
| `test_inference.py` | 50 passed (with `test_retrain_m3.py`) |
| `test_retrain_m3.py` | (above combined) |

### V1 + baseline + existing suites

| Suite | Result |
|-------|--------|
| `test_v1_feature_engineering.py` | PASS |
| `test_v1_training_dataset.py` | PASS |
| `test_v1_baseline_m3.py` | PASS |
| `test_feature_engineering.py` | 54 PASSED |

### Full ML test suite

`python -m pytest ml/tests -q` → **401 passed** (previously could not collect due to 3 broken modules).

### Live verification (unchanged behaviour)

- `ml/verify_v1_training_dataset.py` → VERIFICATION PASSED
- `ml/verify_v1_baseline_m3.py` → baseline reproducible, no model persisted

## 6. Conclusion

The import/module collision is resolved cleanly and backward-compatibly. All tests pass; existing behaviour, contracts, feature definitions, and model behaviour are unchanged. No redesign, no ETL, no DB, no model training.
