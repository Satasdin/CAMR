"""The agent with the engine as its memory, in a process of its own: test_agentic_engine_cases.py holds the cases
(reach sessions over the fake reader, MLX arrays, no model loaded). They run in a child process so the MLX state they
set up never reaches the other tests in this one."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(importlib.util.find_spec("mlx") is None, reason="needs MLX (the Mac)")
def test_the_engine_cases_pass_in_their_own_process(tmp_path):
    here = Path(__file__).parent
    env = {**os.environ, "CAMR_ENGINE_CASES": "1", "CAMR_MEASURING": str(tmp_path / "measuring.json")}
    got = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--rootdir", str(here.parent),
                          str(here / "test_agentic_engine_cases.py")], cwd=here.parent, env=env, capture_output=True,
                         text=True, timeout=300)
    assert got.returncode == 0, got.stdout[-4000:] + got.stderr[-2000:]
    assert "6 passed" in got.stdout
