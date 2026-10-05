"""Exercise real HA entity setup, push updates, lifecycle and freshness."""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from wftnp import ClientState, Notification

from custom_components.wahoo_fitness.const import BIKE_DATA
from custom_components.wahoo_fitness.coordinator import Sample
from custom_components.wahoo_fitness.ftms import Metric


async def setup(hass, entry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry.runtime_data


async def test_setup_push_and_unload(hass, entry, transport):
    coordinator = await setup(hass, entry)
    assert len(hass.states.async_all("sensor")) == 3
    coordinator._notification(Notification(BIKE_DATA, bytes.fromhex("4400b80bb500fa00"), 1))
    await hass.async_block_till_done()
    states = {state.attributes["unit_of_measurement"]: state for state in hass.states.async_all("sensor")}
    assert states["W"].state == "250.0"
    assert states["rpm"].state == "90.5"
    assert states["km/h"].state == "30.0"
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    transport.stop.assert_awaited_once()
    assert coordinator._stopped


async def test_disconnect_reconnect_drops_old_generation(hass, entry, transport):
    coordinator = await setup(hass, entry)
    callback = transport.subscribe.call_args.args[1]
    listener = transport.add_state_listener.call_args.args[0]
    callback(Notification(BIKE_DATA, bytes.fromhex("4400b80bb500fa00"), 1))
    transport.state = ClientState.BACKOFF
    listener(ClientState.BACKOFF)
    await hass.async_block_till_done()
    assert all(s.state == "unavailable" for s in hass.states.async_all("sensor"))
    transport.connection_id = 2
    transport.state = ClientState.RESTORING
    listener(ClientState.RESTORING)
    callback(Notification(BIKE_DATA, bytes.fromhex("4400b80bb500fa00"), 1))
    assert not coordinator.data
    callback(Notification(BIKE_DATA, bytes.fromhex("4400000000000000"), 2))
    transport.state = ClientState.READY
    listener(ClientState.READY)
    await hass.async_block_till_done()
    assert all(s.state == "0.0" for s in hass.states.async_all("sensor"))
    await hass.config_entries.async_unload(entry.entry_id)


async def test_partial_freshness_invalid_data_and_closed_subscription(hass, entry, transport):
    coordinator = await setup(hass, entry)
    coordinator._notification(Notification(BIKE_DATA, bytes.fromhex("4400b80bb500fa00"), 1))
    now = hass.loop.time()
    coordinator.data = {
        metric: replace(sample, received=now - 16) for metric, sample in coordinator.data.items()
    }
    coordinator._notification(Notification(BIKE_DATA, bytes.fromhex("0000e803"), 1))
    coordinator._expire(datetime.now(UTC))
    assert set(coordinator.data) == {Metric.SPEED}
    before = dict(coordinator.data)
    coordinator._notification(Notification(BIKE_DATA, b"bad", 1))
    assert coordinator.data == before
    await hass.async_block_till_done()
    assert sorted(s.state for s in hass.states.async_all("sensor")) == ["10.0", "unavailable", "unavailable"]
    coordinator.data[Metric.POWER] = Sample(None, now)
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert any(s.state == "unknown" for s in hass.states.async_all("sensor"))
    coordinator.subscription.closed = True
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        coordinator._expire(datetime.now(UTC))
        coordinator._expire(datetime.now(UTC))
        reload.assert_called_once_with(entry.entry_id)
    await hass.async_block_till_done()
    assert all(s.state == "unavailable" for s in hass.states.async_all("sensor"))
    await hass.config_entries.async_unload(entry.entry_id)


async def test_failed_setup_closes_transport(hass, entry, transport):
    transport.wait_ready.side_effect = TimeoutError
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_RETRY
    transport.stop.assert_awaited_once()


async def test_identity_mismatch(hass, entry, transport):
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, unique_id="different")
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_ERROR
    transport.stop.assert_awaited_once()


async def test_subscription_failure_cleanup(hass, entry, transport):
    transport.subscribe.side_effect = TimeoutError
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    transport.stop.assert_awaited_once()


async def test_ha_shutdown_closes_client(hass, entry, transport):
    await setup(hass, entry)
    await hass.async_stop()
    transport.stop.assert_awaited_once()


async def test_unload_failure_retains_running_client(hass, entry, transport):
    await setup(hass, entry)
    from unittest.mock import AsyncMock

    from custom_components.wahoo_fitness import async_unload_entry

    with patch.object(hass.config_entries, "async_unload_platforms", AsyncMock(return_value=False)):
        assert not await async_unload_entry(hass, entry)
        transport.stop.assert_not_awaited()
    await hass.config_entries.async_unload(entry.entry_id)


async def test_diagnostics_no_identity_or_workout_values(hass, entry, transport):
    import json

    from custom_components.wahoo_fitness.diagnostics import async_get_config_entry_diagnostics

    await setup(hass, entry)
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    serialized = json.dumps(diagnostics)
    assert entry.unique_id not in serialized
    assert entry.data["host"] not in serialized
    assert diagnostics["profile"] == "bike"
    await hass.config_entries.async_unload(entry.entry_id)
