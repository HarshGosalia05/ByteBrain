"""ML Feature Engineering — V1 Feature Layer.

Provides V1-scoped feature configuration, dataset builder, validation,
training-dataset preparation (train/validation/test split), and M3 baseline
evaluation for the next-semester risk prediction task (M3).

Backward compatibility
----------------------
This package historically coexists with the pre-existing ``ml/src/features.py``
module (the M1/M2/M3/M4 feature-preparation layer).  Because a package takes
import precedence over a same-named module, existing imports such as
``from features import M1_CONTRACT`` and ``from ml.src.features import
M3_CONTRACT, _one_hot_encode`` resolve here.  The public contract objects and
helpers from the legacy module are therefore re-exported below so both styles
of import keep working.  The legacy module itself is loaded under a private
name and its behaviour is unchanged.
"""
import importlib.util
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Re-export the legacy ml/src/features.py module-level API so existing imports
# (M1/M2/M3/M4 contracts and feature-prep helpers) keep resolving through this
# package which shadows the same-named module.  Smallest backward-compatible
# fix — no redesign, no renamed files, identical behaviour.
# ---------------------------------------------------------------------------

_LEGACY_MODULE_NAME = "_features_legacy"

if _LEGACY_MODULE_NAME not in sys.modules:
    _legacy_path = Path(__file__).resolve().parent.parent / "features.py"
    _spec = importlib.util.spec_from_file_location(_LEGACY_MODULE_NAME, _legacy_path)
    _legacy = importlib.util.module_from_spec(_spec)
    sys.modules[_LEGACY_MODULE_NAME] = _legacy
    if _spec and _spec.loader:
        _spec.loader.exec_module(_legacy)
else:
    _legacy = sys.modules[_LEGACY_MODULE_NAME]

# Public names to surface at package level (module-level API of features.py).
_LEGACY_PUBLIC = [
    "FeatureContract",
    "M1_CONTRACT",
    "M2_CONTRACT",
    "M3_CONTRACT",
    "get_contract",
    "get_encoded_feature_names",
    "validate_raw_features",
    "apply_m1_preprocessing",
    "build_m1_features",
    "build_m2m3_features",
    "prepare_m1_inference",
    "prepare_m2_inference",
    "prepare_m3_inference",
    "prepare_m4_inputs",
    "_one_hot_encode",
]
for _name in _LEGACY_PUBLIC:
    globals()[_name] = getattr(_legacy, _name)

# ---------------------------------------------------------------------------
# V1 feature layer public API
# ---------------------------------------------------------------------------

from .v1_config import V1Config  # noqa: E402
from .v1_dataset import V1Dataset, build_v1_dataset  # noqa: E402
from .v1_validation import ValidationResult, validate_v1_dataset  # noqa: E402
from .v1_split_config import V1SplitConfig  # noqa: E402
from .v1_split import PreparedV1Dataset, prepare_v1_dataset  # noqa: E402
from .v1_split_validation import SplitValidationResult, validate_v1_split  # noqa: E402
from .v1_split_coverage import CoverageAssessment, assess_positive_coverage  # noqa: E402
from .v1_baseline_m3 import BaselineResult, FoldMetrics, AggregateMetrics, run_baseline_cv  # noqa: E402
from .v1_model_improvement import (  # noqa: E402
    ModelComparison,
    OverfitAnalysis,
    run_model_improvement,
    comparison_report,
)
from .v1_m3_experiment import (  # noqa: E402
    ExperimentResult,
    ModelResult,
    FoldResult,
    Aggregate,
    run_m3_experiment,
    experiment_report,
    REFERENCE_MODEL,
    MODEL_REGISTRY,
)
from .v1_feedback_audit import (  # noqa: E402
    BoundLabel,
    LabelQualityReport,
    audit_prediction_feedback_labels,
    render_quality_report,
)
from .v1_label_builder import (  # noqa: E402
    OutcomeConflict,
    LabelAuditReport,
    build_academic_labels,
    audit_labels,
    render_label_report,
)
from .v1_m2_regression import (  # noqa: E402
    FoldMetrics as M2FoldMetrics,
    AggregateMetrics as M2AggregateMetrics,
    ModelResult as M2ModelResult,
    TargetResult,
    M2RegressionResult,
    build_m2_regression_frames,
    run_m2_regression,
    m2_regression_report,
    train_and_persist_m2,
)
from .v1_ml_readiness_audit import (  # noqa: E402
    IntegratedAuditResult,
    ModelContractAudit,
    ArtifactAudit,
    run_integrated_audit,
    render_report,
)
from .v1_cohort_dataset import (  # noqa: E402
    V1CohortScope,
    SUPPORTED_DEPARTMENTS,
    build_cohort_v1_dataset,
    report_cohort,
)
from .v1_m3_cohort_expansion import (  # noqa: E402
    M3CohortExpansionAnalysis,
    analyze_m3_cohort_expansion,
    render_expansion_analysis,
)
from .v1_m3_validation_gate import (  # noqa: E402
    GateVerdict,
    DataSufficiency,
    FoldDetail,
    M3ValidationGateResult,
    compute_m3_validation_gate,
    run_m3_validation_gate,
    render_gate_report,
)
from .v1_later_cohort_gate import (  # noqa: E402
    LaterCohortCandidate,
    LaterCohortGateResult,
    run_later_cohort_gate,
    render_later_cohort_gate,
    VALID,
    NO_VALID,
    INSUFFICIENT,
)
from .v1_etl_second_cohort_readiness import (  # noqa: E402
    ETL_READY,
    ETL_MINOR,
    ETL_BLOCKED,
    EtlCapability,
    EtlEnforcedScope,
    SecondCohortReadinessResult,
    SecondCohortValidation,
    audit_etl_second_cohort_readiness,
    render_readiness_audit,
    validate_second_cohort_payload,
)
from .v1_inference_contract import (  # noqa: E402
    READY,
    BLOCKED,
    UNAVAILABLE,
    INVALID_INPUT,
    ERROR,
    SUPPORTED_MODEL_IDS,
    READINESS_STATES,
    MODEL_READINESS,
    MODEL_READINESS_REASON,
    MODEL_ALGORITHM,
    M1_ENCODED_FEATURES,
    M2_M3_ENCODED_FEATURES,
    InferenceResult,
    InferenceInputError,
    supported_models,
    get_readiness,
    readiness_reason,
    validate_input_row,
    feature_names,
    artifact_hash,
    predict,
    predict_m1,
    predict_m2,
    predict_m3,
)

__all__ = [
    "V1Config",
    "V1Dataset",
    "build_v1_dataset",
    "ValidationResult",
    "validate_v1_dataset",
    "V1SplitConfig",
    "PreparedV1Dataset",
    "prepare_v1_dataset",
    "SplitValidationResult",
    "validate_v1_split",
    "CoverageAssessment",
    "assess_positive_coverage",
    "BaselineResult",
    "FoldMetrics",
    "AggregateMetrics",
    "run_baseline_cv",
    "ModelComparison",
    "OverfitAnalysis",
    "run_model_improvement",
    "comparison_report",
    "ExperimentResult",
    "ModelResult",
    "FoldResult",
    "Aggregate",
    "run_m3_experiment",
    "experiment_report",
    "REFERENCE_MODEL",
    "MODEL_REGISTRY",
    "BoundLabel",
    "LabelQualityReport",
    "audit_prediction_feedback_labels",
    "render_quality_report",
    "OutcomeConflict",
    "LabelAuditReport",
    "build_academic_labels",
    "audit_labels",
    "render_label_report",
    "M2FoldMetrics",
    "M2AggregateMetrics",
    "M2ModelResult",
    "TargetResult",
    "M2RegressionResult",
    "build_m2_regression_frames",
    "run_m2_regression",
    "m2_regression_report",
    "train_and_persist_m2",
    "IntegratedAuditResult",
    "ModelContractAudit",
    "ArtifactAudit",
    "run_integrated_audit",
    "render_report",
    "V1CohortScope",
    "SUPPORTED_DEPARTMENTS",
    "build_cohort_v1_dataset",
    "report_cohort",
    "M3CohortExpansionAnalysis",
    "analyze_m3_cohort_expansion",
    "render_expansion_analysis",
    "GateVerdict",
    "DataSufficiency",
    "FoldDetail",
    "M3ValidationGateResult",
    "compute_m3_validation_gate",
    "run_m3_validation_gate",
    "render_gate_report",
    "LaterCohortCandidate",
    "LaterCohortGateResult",
    "run_later_cohort_gate",
    "render_later_cohort_gate",
    "VALID",
    "NO_VALID",
    "INSUFFICIENT",
    "ETL_READY",
    "ETL_MINOR",
    "ETL_BLOCKED",
    "EtlCapability",
    "EtlEnforcedScope",
    "SecondCohortReadinessResult",
    "SecondCohortValidation",
    "audit_etl_second_cohort_readiness",
    "render_readiness_audit",
    "validate_second_cohort_payload",
    # Unified offline inference contract
    "READY",
    "BLOCKED",
    "UNAVAILABLE",
    "INVALID_INPUT",
    "ERROR",
    "SUPPORTED_MODEL_IDS",
    "READINESS_STATES",
    "MODEL_READINESS",
    "MODEL_READINESS_REASON",
    "MODEL_ALGORITHM",
    "M1_ENCODED_FEATURES",
    "M2_M3_ENCODED_FEATURES",
    "InferenceResult",
    "InferenceInputError",
    "supported_models",
    "get_readiness",
    "readiness_reason",
    "validate_input_row",
    "feature_names",
    "artifact_hash",
    "predict",
    "predict_m1",
    "predict_m2",
    "predict_m3",
    # Re-exported legacy module API
    "FeatureContract",
    "M1_CONTRACT",
    "M2_CONTRACT",
    "M3_CONTRACT",
    "get_contract",
    "get_encoded_feature_names",
    "validate_raw_features",
    "apply_m1_preprocessing",
    "build_m1_features",
    "build_m2m3_features",
    "prepare_m1_inference",
    "prepare_m2_inference",
    "prepare_m3_inference",
    "prepare_m4_inputs",
    "_one_hot_encode",
]
