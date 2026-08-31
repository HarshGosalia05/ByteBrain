"""Quick import test for M1 v2 package."""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))

print("Testing M1 v2 imports...")

from v2.m1_subject_prediction import config
print(f"  config: OK - MODEL_NAME={config.MODEL_NAME}")

from v2.m1_subject_prediction.data.loader import SupabaseLoader
print(f"  loader: OK")

from v2.m1_subject_prediction.features.builder import build_feature_matrix, check_joins
print(f"  features.builder: OK")

from v2.m1_subject_prediction.preprocessing.pipeline import M1Preprocessor, select_features
print(f"  preprocessing: OK")

from v2.m1_subject_prediction.validation.cv import (
    make_model, run_group_kfold_cv, run_temporal_holdout
)
print(f"  validation.cv: OK")

from v2.m1_subject_prediction.inference.predictor import M1V2Predictor, get_predictor
print(f"  inference.predictor: OK")

print("\nAll imports: PASS")
print(f"  Target: {config.TARGET}")
print(f"  Training sems: {config.TRAINING_SEMESTERS}")
print(f"  Holdout sem: {config.TEMPORAL_HOLDOUT_SEMESTER}")
print(f"  Algorithms: {config.MODEL_ALGORITHMS}")
print(f"  Feature tiers: T1={len(config.TIER1_NUMERIC + config.TIER1_BEHAVIORAL + config.TIER1_CATEGORICAL + config.TIER1_STUDENT_META)}, T2={len(config.TIER2_PRIOR_HISTORY)}")
print(f"  Forbidden features: {len(config.FORBIDDEN_FEATURES)}")
