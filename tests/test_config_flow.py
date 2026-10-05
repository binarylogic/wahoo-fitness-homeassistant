"""Config flows validate equipment identity before creating or updating entries."""

from dataclasses import replace
from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from custom_components.wahoo_fitness.const import DOMAIN, SERVICE_TYPE
from custom_components.wahoo_fitness.device import UnsupportedDevice


@pytest.fixture
def probe(device):
    with patch("custom_components.wahoo_fitness.config_flow.probe", AsyncMock(return_value=device)) as mock:
        yield mock


async def test_manual(hass, probe):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] == FlowResultType.FORM
    with patch("custom_components.wahoo_fitness.async_setup_entry", AsyncMock(return_value=True)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": " bike.local ", "port": 36866}
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "test-serial"
    assert result["data"] == {"host": "bike.local", "port": 36866}


@pytest.mark.parametrize(
    "error,expected", [(TimeoutError(), "cannot_connect"), (UnsupportedDevice(), "unsupported_device")]
)
async def test_error(hass, probe, error, expected):
    probe.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={"host": "bike.local", "port": 36866}
    )
    assert result["errors"] == {"base": expected}


def advertisement():
    return ZeroconfServiceInfo(
        ip_address=ip_address("192.0.2.2"),
        ip_addresses=[ip_address("192.0.2.2")],
        port=36866,
        hostname="bike.local.",
        type=SERVICE_TYPE,
        name="KICKR BIKE Test." + SERVICE_TYPE,
        properties={},
    )


async def test_discovery(hass, probe):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=advertisement()
    )
    assert result["step_id"] == "zeroconf_confirm"
    with patch("custom_components.wahoo_fitness.async_setup_entry", AsyncMock(return_value=True)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "KICKR BIKE Test"


async def test_discovery_updates_duplicate_endpoint(hass, entry, probe):
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=advertisement()
    )
    assert result["reason"] == "already_configured"
    assert entry.data["host"] == "192.0.2.2"


@pytest.mark.parametrize("mismatch", [False, True])
async def test_reconfigure_identity(hass, entry, probe, device, mismatch):
    entry.add_to_hass(hass)
    if mismatch:
        probe.return_value = replace(device, serial="another")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
    )
    with patch.object(hass.config_entries, "async_reload", AsyncMock()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "new.local", "port": 36866}
        )
        await hass.async_block_till_done()
    assert result["reason"] == ("unique_id_mismatch" if mismatch else "reconfigure_successful")
    assert entry.data["host"] == ("bike.local" if mismatch else "new.local")


@pytest.mark.parametrize(
    "error,expected", [(TimeoutError(), "cannot_connect"), (UnsupportedDevice(), "unsupported_device")]
)
async def test_discovery_errors(hass, probe, error, expected):
    probe.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=advertisement()
    )
    assert result["reason"] == expected


async def test_probe_stops_on_inspection_failure(client):
    from custom_components.wahoo_fitness.config_flow import probe as real_probe

    with (
        patch("custom_components.wahoo_fitness.config_flow.WftnpClient", return_value=client),
        patch(
            "custom_components.wahoo_fitness.config_flow.inspect_device",
            AsyncMock(side_effect=UnsupportedDevice),
        ),
    ):
        with pytest.raises(UnsupportedDevice):
            await real_probe("bike.local", 36866)
    client.stop.assert_awaited_once()
