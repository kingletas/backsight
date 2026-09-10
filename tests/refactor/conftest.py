"""Fixtures for the refactor corpus."""

import pytest
from corpus import Case, cases


@pytest.fixture(params=cases(), ids=lambda c: c.name)
def case(request) -> Case:
    return request.param
