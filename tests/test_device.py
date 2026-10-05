"""Capability inspection uses only advertised, readable attributes."""

from unittest.mock import AsyncMock, Mock

import pytest
from wftnp import Characteristic, Service
from wftnp import CharacteristicProperties as P

from custom_components.wahoo_fitness.const import (
    BIKE_DATA,
    DEVICE_INFORMATION,
    FITNESS_FEATURE,
    FITNESS_MACHINE,
    SERIAL_NUMBER,
    TREADMILL_DATA,
)
from custom_components.wahoo_fitness.device import UnsupportedDevice, inspect_device
from custom_components.wahoo_fitness.ftms import Profile


@pytest.fixture
def peer():
    peer = Mock()
    peer.discover_services = AsyncMock(return_value=[Service(FITNESS_MACHINE), Service(DEVICE_INFORMATION)])

    async def characteristics(service):
        return (
            [Characteristic(BIKE_DATA, P.NOTIFY), Characteristic(FITNESS_FEATURE, P.READ)]
            if service == FITNESS_MACHINE
            else [Characteristic(SERIAL_NUMBER, P.READ)]
        )

    peer.discover_characteristics = AsyncMock(side_effect=characteristics)
    peer.read_characteristic = AsyncMock(
        side_effect=lambda uuid: (
            bytes.fromhex("0240000008600000") if uuid == FITNESS_FEATURE else b"test-serial\x00"
        )
    )
    return peer


async def test_minimum_identity_and_capabilities(peer):
    device = await inspect_device(peer)
    assert device.serial == "test-serial"
    assert device.profile == Profile.BIKE
    assert device.model == "Indoor bike"
    assert device.firmware is None
    assert peer.read_characteristic.await_count == 2


async def test_services_required(peer):
    peer.discover_services.return_value = []
    with pytest.raises(UnsupportedDevice):
        await inspect_device(peer)


@pytest.mark.parametrize(
    "chars",
    [
        [],
        [Characteristic(BIKE_DATA, P.READ)],
        [
            Characteristic(BIKE_DATA, P.NOTIFY),
            Characteristic(TREADMILL_DATA, P.NOTIFY),
            Characteristic(FITNESS_FEATURE, P.READ),
        ],
    ],
)
async def test_invalid_profiles(peer, chars):
    peer.discover_characteristics.side_effect = None
    peer.discover_characteristics.return_value = chars
    with pytest.raises(UnsupportedDevice):
        await inspect_device(peer)


async def test_invalid_feature_length(peer):
    peer.read_characteristic.side_effect = None
    peer.read_characteristic.return_value = b"bad"
    with pytest.raises(UnsupportedDevice):
        await inspect_device(peer)


async def test_missing_serial(peer):
    peer.read_characteristic.side_effect = lambda uuid: bytes(8) if uuid == FITNESS_FEATURE else b"\x00"
    with pytest.raises(UnsupportedDevice):
        await inspect_device(peer)
