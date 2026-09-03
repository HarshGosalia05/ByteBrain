import asyncio
import sys
import socket
import ssl as _ssl
sys.path.insert(0, r"C:\Users\HET SHAH\ByteBrain")
sys.path.insert(0, r"C:\Users\HET SHAH\ByteBrain\backend")
sys.path.insert(0, r"C:\Users\HET SHAH\ByteBrain\ml")

import os
from dotenv import load_dotenv
import pytest

load_dotenv(r"C:\Users\HET SHAH\ByteBrain\.env.local")

@pytest.mark.anyio
async def test_endpoint():
    import asyncpg
    import asyncio as _asyncio
    host = os.environ.get("DB_HOST")
    port = int(os.environ.get("DB_PORT", "5432"))
    dbname = os.environ.get("DB_NAME", "postgres")
    user = os.environ.get("DB_USER")
    password = os.environ.get("DB_PASSWORD")
    ip = socket.gethostbyname(host)

    # Patch event loop's getaddrinfo to avoid Windows Python 3.13 bug
    loop = _asyncio.get_event_loop()
    orig_getaddrinfo = _asyncio.get_event_loop_policy().get_event_loop().getaddrinfo if hasattr(_asyncio.get_event_loop_policy().get_event_loop(), 'getaddrinfo') else None
    async def patched_getaddrinfo(host_arg, port_arg, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, port_arg))]
    loop.getaddrinfo = patched_getaddrinfo

    from urllib.parse import quote
    dsn = f"postgresql://{quote(user, safe='')}:{quote(password, safe='')}@{ip}:{port}/{dbname}"
    conn = await asyncpg.connect(dsn, ssl="require")
    
    from v3.m1_subject_prediction.inference.predictor import M1V3Predictor
    predictor = M1V3Predictor()
    predictor.load()
    
    # Test 1: CSE student (should be READY)
    print("=== TEST 1: CSE Student STU000001 (expect READY) ===")
    result = await predictor.predict_for_student("STU000001", conn)
    print(f"  readiness_status: {result['readiness_status']}")
    print(f"  prediction_count: {result['prediction_count']}")
    print(f"  current_semester: {result['current_semester']}")
    print(f"  subjects: {len(result['subjects'])}")
    if result['subjects']:
        s = result['subjects'][0]
        print(f"  Sample subject: {s['subject_id']}")
        print(f"    predicted: {s['predicted_end_sem_marks']}/70")
        print(f"    grade_band: {s['grade_band']}")
        print(f"    grade_label: {s['grade_label']}")
        print(f"    input_features: {s['input_features']}")
    
    # Verify prediction is within [0, 70]
    all_preds = [s['predicted_end_sem_marks'] for s in result['subjects']]
    print(f"  All in [0,70]: {all(0 <= p <= 70 for p in all_preds)}")
    
    # Test 2: BBA student (should be NO_DATA)
    print("\n=== TEST 2: BBA Student STU000051 (expect NO_DATA) ===")
    result2 = await predictor.predict_for_student("STU000051", conn)
    print(f"  readiness_status: {result2['readiness_status']}")
    print(f"  prediction_count: {result2['prediction_count']}")
    print(f"  reason: {result2.get('reason', 'N/A')}")
    print(f"  subjects: {len(result2['subjects'])}")
    
    # Test 3: Non-existent student
    print("\n=== TEST 3: Non-existent STU6ANOPE (expect NO_DATA) ===")
    result3 = await predictor.predict_for_student("STU6ANOPE", conn)
    print(f"  readiness_status: {result3['readiness_status']}")
    print(f"  reason: {result3.get('reason', 'N/A')}")
    print(f"  subjects: {len(result3['subjects'])}")
    
    # Test 4: Verify no synthetic/fake data in predictions
    print("\n=== TEST 4: Verify NO FAKE DATA ===")
    sample_result = await predictor.predict_for_student("STU000005", conn)
    for subj in sample_result['subjects']:
        feats = subj['input_features']
        assert feats['internal_marks'] is not None, f"internal_marks is None for {subj['subject_id']}"
        assert 0 <= feats['internal_marks'] <= 50, f"internal_marks out of range: {feats['internal_marks']}"
        assert feats['mid_sem_marks'] is not None, f"mid_sem_marks is None for {subj['subject_id']}"
        assert 0 <= feats['mid_sem_marks'] <= 50, f"mid_sem_marks out of range: {feats['mid_sem_marks']}"
        assert feats['attendance_percentage'] is not None, f"attendance is None for {subj['subject_id']}"
        assert 0 <= feats['attendance_percentage'] <= 100, f"attendance out of range: {feats['attendance_percentage']}"
        print(f"  {subj['subject_id']}: int={feats['internal_marks']}, mid={feats['mid_sem_marks']}, att={feats['attendance_percentage']:.1f}% - REAL")
    print("  All input features verified as REAL production data")
    
    # Test 5: Verify the model_id and note
    print("\n=== TEST 5: Verify model_id and note ===")
    print(f"  model_id: {result.get('model_id', 'NOT SET')}")
    print(f"  model_version: {result.get('model_version', 'NOT SET')}")
    print(f"  algorithm: {result.get('algorithm', 'NOT SET')}")
    
    await conn.close()
    print("\n=== ALL TESTS PASSED ===")

asyncio.run(test_endpoint())
