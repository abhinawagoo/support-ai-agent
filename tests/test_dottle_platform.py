"""Pytest wrapper for Dottle scenario catalog (requires DOTTLE_API_KEY)."""

from __future__ import annotations

import os

import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.skipif(not (os.getenv("DOTTLE_API_KEY") or "").strip(), reason="DOTTLE_API_KEY not set")
def test_dottle_scenarios_sync() -> None:
    os.environ["DOTTLE_TEST_SYNC"] = "1"
    from tests.dottle_platform.scenarios import SCENARIOS

    for _name, fn in SCENARIOS:
        fn()
