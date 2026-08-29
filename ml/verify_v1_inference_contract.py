"""READ-ONLY live verification of the Unified OFFLINE Inference Contract.

Executes the same checks as the focused test-suite but against REAL existing
project data (the CSV mirror of the authoritative DB) plus the authoritative
artifacts.  This script makes NO database writes, NO artifact writes, and NO
model training.

Verified:
- M1 loads + scores valid real existing inference input (clipped to [0,70]).
- M2 loads + scores valid real existing inference input.
- M3 correctly remains BLOCKED (prediction_available=False).
- Feature contracts are the exact 12-feature set/order incl. BBA/CSE.
- Prediction outputs are finite where allowed.
- M1 outputs within [0,70].
- Repeated runs are deterministic.
- Artifacts remain byte-identical (SHA-256) throughout.
- No database writes occur.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np

_ML_SRC = str(Path(__file__).resolve().parent / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

from m1 import data as m1_data  # real CSV table loader (read-only)  # noqa: E402
from features.v1_inference_contract import (  # noqa: E402
    READY,
    BLOCKED,
    READINESS_STATES,
    M1_ENCODED_FEATURES,
    M2_M3_ENCODED_FEATURES,
    InferenceInputError,
    get_readiness,
    feature_names,
    artifact_hash,
    predict_m1,
    predict_m2,
    predict_m3,
)

KNOWN_HASHES = {
    "m1": "3404D29EE61C151C39B50CB9F00D9EE268B8CAF7B39F8BB24D01F17EBFC6431E",
    "m2": "6CAC9A884ABAEF16575D7B866405A726F751BEFC18359C3C599AFDB5E071C012",
    "m3": "99D845FE64A9002B7B1176975A0B41CF29F16A57D380993DA260E2557E2044A7",
}

_results = []
_ok = True


def check(label: str, condition: bool, detail: str = "") -> None:
    global _ok
    _results.append((label, condition, detail))
    if not condition:
        _ok = False


def main() -> int:
    tables = m1_data.load_tables()
    performance = tables["performance"]
    summary = tables["summary"]
    students = tables["students"]

    # ------------------------------------------------------------------
    # Build ONE genuine M1 inference row from REAL data.
    # ------------------------------------------------------------------
    perf = performance.iloc[0]
    sub = tables["subjects"][tables["subjects"]["subject_id"] == perf["subject_id"]].iloc[0]
    std = students[students["student_id"] == perf["student_id"]].iloc[0]
    att = tables["attendance"][
        tables["attendance"]["enrollment_record_id"] == perf["enrollment_record_id"]
    ].iloc[0]
    m1_row = {
        "student_id": str(perf["student_id"]),
        "subject_id": str(perf["subject_id"]),
        "semester_no": int(perf["semester_no"]),
        "internal_marks": float(perf["internal_marks"]),
        "mid_sem_marks": float(perf["mid_sem_marks"]),
        "attendance_percentage": float(att["attendance_percentage"]),
        "credits": float(sub["credits"]),
        "subject_type": str(sub["subject_type"]),
        "department_name": str(std["department_name"]),
        "gender": str(std["gender"]),
    }

    # Build ONE genuine M2/M3 inference row from REAL data.
    sm = summary.iloc[0]
    sstd = students[students["student_id"] == sm["student_id"]].iloc[0]
    m23_row = {
        "student_id": str(sm["student_id"]),
        "semester_no": int(sm["semester_no"]),
        "subjects_registered": float(sm["subjects_registered"]),
        "credits_registered": float(sm["credits_registered"]),
        "credits_earned": float(sm["credits_earned"]),
        "semester_total_marks": float(sm["semester_total_marks"]),
        "semester_percentage": float(sm["semester_percentage"]),
        "semester_sgpa": float(sm["semester_sgpa"]),
        "semester_attendance_percentage": float(sm["semester_attendance_percentage"]),
        "backlog_count": float(sm["backlog_count"]),
        "department_name": str(sstd["department_name"]),
        "gender": str(sstd["gender"]),
    }

    check("real data loaded", len(performance) > 0 and len(summary) > 0)

    # ------------------------------------------------------------------
    # Readiness states.
    # ------------------------------------------------------------------
    check("M1 readiness READY", get_readiness("m1") == READY)
    check("M2 readiness READY", get_readiness("m2") == READY)
    check("M3 readiness BLOCKED", get_readiness("m3") == BLOCKED)

    # ------------------------------------------------------------------
    # Feature contracts (exact 12 + order + BBA/CSE).
    # ------------------------------------------------------------------
    m1_names = feature_names("m1")
    m2_names = feature_names("m2")
    m3_names = feature_names("m3")
    check("M1 12-feature contract", len(m1_names) == 12 and list(m1_names) == list(M1_ENCODED_FEATURES))
    check("M2 12-feature contract", len(m2_names) == 12 and list(m2_names) == list(M2_M3_ENCODED_FEATURES))
    check("M3 12-feature contract", len(m3_names) == 12 and list(m3_names) == list(M2_M3_ENCODED_FEATURES))
    for nm in (m1_names, m2_names, m3_names):
        check("BBA/CSE one-hot present", "department_name_BBA" in nm and "department_name_CSE" in nm)
    check("BBA/CSE exact order", m2_names[-3:] == ["department_name_BBA", "department_name_CSE", "is_male"])

    # ------------------------------------------------------------------
    # M1 prediction (finite + clipped to [0,70]).
    # ------------------------------------------------------------------
    r1 = predict_m1(dict(m1_row))
    check("M1 ready/available", r1.readiness_status == READY and r1.prediction_available)
    check("M1 prediction finite", np.isfinite(float(r1.prediction)))
    check("M1 prediction in [0,70]", 0.0 <= r1.prediction <= 70.0)
    check("M1 feature_count 12", r1.feature_count == 12)

    # ------------------------------------------------------------------
    # M2 prediction (finite outputs).
    # ------------------------------------------------------------------
    r2 = predict_m2(dict(m23_row))
    check("M2 ready/available", r2.readiness_status == READY and r2.prediction_available)
    check("M2 percentage finite", np.isfinite(float(r2.prediction["next_semester_percentage"])))
    check("M2 sgpa finite", np.isfinite(float(r2.prediction["next_semester_sgpa"])))
    check("M2 feature_count 12", r2.feature_count == 12)

    # ------------------------------------------------------------------
    # M3 stays BLOCKED.
    # ------------------------------------------------------------------
    r3 = predict_m3(dict(m23_row))
    check("M3 blocked", r3.readiness_status == BLOCKED)
    check("M3 prediction unavailable", r3.prediction_available is False)
    check("M3 no normal prediction", r3.prediction is None)

    # ------------------------------------------------------------------
    # Determinism: repeat each READY model at least twice; M3 twice too.
    # ------------------------------------------------------------------
    check("M1 deterministic", predict_m1(dict(m1_row)).to_dict() == r1.to_dict())
    check("M2 deterministic", predict_m2(dict(m23_row)).to_dict() == r2.to_dict())
    check("M3 deterministic blocked", predict_m3(dict(m23_row)).to_dict() == r3.to_dict())
    r1b = predict_m1(dict(m1_row)).to_dict()
    r2b = predict_m2(dict(m23_row)).to_dict()
    check("M1 deterministic (3rd run)", r1b == predict_m1(dict(m1_row)).to_dict())
    check("M2 deterministic (3rd run)", r2b == predict_m2(dict(m23_row)).to_dict())
    m3off = predict_m3(dict(m23_row), allow_offline_score=True)
    check("M3 offline still BLOCKED",
          m3off.readiness_status == BLOCKED and m3off.prediction_available is False)

    # ------------------------------------------------------------------
    # Artifact hashes unchanged (before==after == known).
    # ------------------------------------------------------------------
    for mid in ("m1", "m2", "m3"):
        h = artifact_hash(mid)
        check(f"{mid} hash == known", h == KNOWN_HASHES[mid], h)

    # ------------------------------------------------------------------
    # No DB writes: this module uses only in-memory frames; assert the
    # source never connects to a database.
    # ------------------------------------------------------------------
    from features import v1_inference_contract as contract
    src = open(contract.__file__, encoding="utf-8").read()
    check("no DB write code", all(tok not in src for tok in ("asyncpg", "psycopg", "INSERT INTO", "UPDATE", "DELETE FROM")))
    check("no artifact write code", "joblib.dump" not in src and "to_pickle" not in src)

    # ------------------------------------------------------------------
    # Report.
    # ------------------------------------------------------------------
    print("=" * 72)
    print("UNIFIED OFFLINE INFERENCE CONTRACT — READ-ONLY LIVE VERIFICATION")
    print("=" * 72)
    passed = sum(1 for _, c, _ in _results if c)
    failed = len(_results) - passed
    for label, cond, detail in _results:
        mark = "PASS" if cond else "FAIL"
        print(f"  [{mark}] {label}" + (f"  ({detail})" if detail and not cond else ""))
    print("-" * 72)
    print(f"  passed = {passed} | failed = {failed} | total = {len(_results)}")
    print("  VERDICT:", "ALL CHECKS PASS" if _ok else "CHECK FAILURE")
    print("=" * 72)
    return 0 if _ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
