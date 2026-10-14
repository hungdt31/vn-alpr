import pytest

from tests.helpers import FakeClock


@pytest.fixture
def clock():
    return FakeClock()
