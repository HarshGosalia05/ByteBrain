import sys
from pathlib import Path

# Ensure ByteBrain root is on sys.path so ml module can be imported
_BYTEBRAIN_ROOT = str(Path(__file__).resolve().parents[2])
if _BYTEBRAIN_ROOT not in sys.path:
    sys.path.insert(0, _BYTEBRAIN_ROOT)

