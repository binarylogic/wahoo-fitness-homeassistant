"""Home Assistant fixtures; hardware is always explicitly opted in."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from wftnp import ClientState

from custom_components.wahoo_fitness.const import DOMAIN
from custom_components.wahoo_fitness.device import Device
from custom_components.wahoo_fitness.ftms import Profile


def pytest_addoption(parser):
    parser.addoption("--hardware", action="store_true")
    parser.addoption("--hardware-config", default=".hardware.toml")


def pytest_ignore_collect(collection_path, config):
    return "hardware" in collection_path.parts and not config.getoption("--hardware")


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def device():
    return Device("test-serial", "Wahoo", "KICKR BIKE", "1.2.3", Profile.BIKE, 0x4002)


@pytest.fixture
def entry():
    return MockConfigEntry(
        domain=DOMAIN, title="KICKR BIKE", unique_id="test-serial", data={"host": "bike.local", "port": 36866}
    )


@pytest.fixture
def client():
    client = Mock(state=ClientState.READY, connection_id=1)
    client.start = AsyncMock()
    client.stop = AsyncMock()
    client.wait_ready = AsyncMock()
    client.subscribe = AsyncMock(return_value=Mock(closed=False, error=None))
    client.add_state_listener = Mock(return_value=Mock())
    return client


@pytest.fixture
def transport(client, device):
    with (
        patch("custom_components.wahoo_fitness.WftnpClient", return_value=client),
        patch("custom_components.wahoo_fitness.inspect_device", AsyncMock(return_value=device)),
    ):
        yield client
