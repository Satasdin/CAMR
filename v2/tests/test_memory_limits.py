"""MLX's cache of freed buffers is capped when a model loads, and the process's real footprint can be read."""

import sys

import pytest

from engram import models


@pytest.mark.skipif(sys.platform != "darwin", reason="libproc is macOS's")
def test_the_footprint_is_this_processs_and_counts_what_it_holds():
    before = models.footprint_bytes()
    block = bytearray(64 * 1024 * 1024)  # 64 MB, touched
    for i in range(0, len(block), 4096):
        block[i] = 1
    after = models.footprint_bytes()
    assert before and after and after - before > 48 * 1024 * 1024
    assert models.footprint_bytes(pid=1) is None or models.footprint_bytes(pid=1) > 0  # another's, if allowed


def test_the_cache_cap_is_set_unless_turned_off():
    mx = pytest.importorskip("mlx.core")
    assert models.limit_cache("off") is None
    assert models.limit_cache(0.5) == 500_000_000
    assert mx.set_cache_limit(models.limit_cache(1.0)) == 1_000_000_000  # set_cache_limit returns the cap before
    models.limit_cache()
