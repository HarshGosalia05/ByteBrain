"""M1 v2 — Subject Performance Predictor.

Top-level package for the M1 v2 production implementation.
Built on the 1200-student CSE 6A cohort in Supabase.

DO NOT import from ml.src.m1 — this is an isolated v2 implementation.
Supabase is READ-ONLY.
"""
from . import config

__version__ = "2.0.0"
__model_name__ = config.MODEL_NAME
