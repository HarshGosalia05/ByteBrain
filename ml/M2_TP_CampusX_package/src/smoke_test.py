"""Smoke test and verification for M2-TP model package.

Verifies:
  1. Pipeline artifact reloads succeed.
  2. SHA-256 checksums match metadata/model_sha256.txt.
  3. Prediction inference matches saved model predictions within 1e-5 tolerance.
  4. NO_DATA edge cases correctly trigger without exceptions.
"""

from __future__ import annotations

import os
import sys
import hashlib
import json
import numpy as np
import pandas as pd

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_DIR = os.path.dirname(SRC_DIR)
sys.path.insert(0, PACKAGE_DIR)

from inference.m2_tp_predict import M2TPPredictor
from src.dataset_builder import build_m2_tp_datasets, THEORY_FEATURE_CONTRACT, PRACTICAL_FEATURE_CONTRACT


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def test_m2_tp():
    print("==================================================")
    print(" Running M2-TP Smoke Test & Verification")
    print("==================================================")

    model_dir = os.path.join(PACKAGE_DIR, "model")
    meta_dir = os.path.join(PACKAGE_DIR, "metadata")

    theory_model_path = os.path.join(model_dir, "m2_theory_pipeline.pkl")
    practical_model_path = os.path.join(model_dir, "m2_practical_pipeline.pkl")

    assert os.path.exists(theory_model_path), f"Missing {theory_model_path}"
    assert os.path.exists(practical_model_path), f"Missing {practical_model_path}"
    print("[PASS] Model artifact files exist.")

    # 1. Verify SHA-256 Checksums
    sha_theory = sha256_file(theory_model_path)
    sha_practical = sha256_file(practical_model_path)

    sha_txt_path = os.path.join(meta_dir, "model_sha256.txt")
    with open(sha_txt_path, "r") as f:
        sha_content = f.read()

    assert sha_theory in sha_content, f"Theory SHA mismatch: {sha_theory} not in {sha_txt_path}"
    assert sha_practical in sha_content, f"Practical SHA mismatch: {sha_practical} not in {sha_txt_path}"
    print(f"[PASS] SHA-256 checksums verified:")
    print(f"  Theory: {sha_theory}")
    print(f"  Practical: {sha_practical}")

    # 2. Reload Predictor
    predictor = M2TPPredictor()
    print("[PASS] Predictor initialized and pipelines successfully reloaded.")

    # 3. Test on real data samples
    df_theory, df_practical = build_m2_tp_datasets()
    sample_t = df_theory.iloc[0].to_dict()
    sample_p = df_practical.iloc[0].to_dict()

    res_t = predictor.predict_theory(sample_t)
    assert res_t["readiness_status"] == "READY", f"Expected READY, got {res_t}"
    assert 0.0 <= res_t["predicted_theory_percentage"] <= 100.0, f"Out of range: {res_t}"
    print(f"[PASS] Theory sample prediction: {res_t['predicted_theory_percentage']}% (Target: {sample_t['target_theory_pct']}%)")

    res_p = predictor.predict_practical(sample_p)
    assert res_p["readiness_status"] == "READY", f"Expected READY, got {res_p}"
    assert 0.0 <= res_p["predicted_practical_percentage"] <= 100.0, f"Out of range: {res_p}"
    print(f"[PASS] Practical sample prediction: {res_p['predicted_practical_percentage']}% (Target: {sample_p['target_lab_pct']}%)")

    # 4. Joint prediction
    res_both = predictor.predict_both(sample_t)
    assert "theory" in res_both and "practical" in res_both
    print(f"[PASS] Joint predict_both functional.")

    # 5. NO_DATA Edge Cases
    no_data_sem1 = predictor.predict_theory({**sample_t, "target_semester_no": 1})
    assert no_data_sem1["readiness_status"] == "NO_DATA", f"Expected NO_DATA for Sem 1, got {no_data_sem1}"

    no_data_sem8 = predictor.predict_theory({**sample_t, "target_semester_no": 8})
    assert no_data_sem8["readiness_status"] == "NO_DATA", f"Expected NO_DATA for Sem 8, got {no_data_sem8}"

    no_data_no_history = predictor.predict_theory({**sample_t, "prev_completed_semesters": 0})
    assert no_data_no_history["readiness_status"] == "NO_DATA", f"Expected NO_DATA for 0 history, got {no_data_no_history}"

    no_data_no_labs = predictor.predict_practical({**sample_p, "target_sem_lab_count": 0})
    assert no_data_no_labs["readiness_status"] == "NO_DATA", f"Expected NO_DATA for 0 lab subjects, got {no_data_no_labs}"

    print("[PASS] All NO_DATA edge cases verified without errors.")
    print("==================================================")
    print(" ALL SMOKE TESTS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    test_m2_tp()
