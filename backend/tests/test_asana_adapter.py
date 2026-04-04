from __future__ import annotations

import os

import pytest

from backend.app.adapters.asana.service import list_sections


@pytest.mark.skipif(not os.getenv("ASANA_PAT"), reason="ASANA_PAT is not configured")
def test_list_sections() -> None:
    sections = __import__("asyncio").run(list_sections())
    assert isinstance(sections, list)
