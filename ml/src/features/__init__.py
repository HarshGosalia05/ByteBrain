"""ML Feature Engineering — V1 Feature Layer.

Provides V1-scoped feature configuration, dataset builder, and validation
for the next-semester risk prediction task (M3).
"""
from .v1_config import V1Config
from .v1_dataset import V1Dataset, build_v1_dataset
from .v1_validation import ValidationResult, validate_v1_dataset

__all__ = [
    "V1Config",
    "V1Dataset",
    "build_v1_dataset",
    "ValidationResult",
    "validate_v1_dataset",
]
