"""Compatibility entry point. The build pipeline lives in akynoleyend/build.py."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from akynoleyend.cli import main
if __name__ == "__main__":
    raise SystemExit(main(["build", *sys.argv[1:]]))
