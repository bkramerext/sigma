#!/usr/bin/env python3
"""Run several saved SIGMA research sessions concurrently from a JSON spec."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sigma.research_batch import main

if __name__ == "__main__":
    main()
