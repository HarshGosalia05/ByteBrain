"""
Phase 14 - Experimental M1_v3
=============================
NEW experimental M1_v3 (NOT the production M1_v3).
Uses the strongest justified feature/model combination from prior experiments.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _train_hgb import run

if __name__ == "__main__":
    run("m1_v3")