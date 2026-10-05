"""Real FTMS decoding through actual HA sensors and forced socket reconnection."""

import asyncio

import pytest
import pytest_socket
from pytest_homeassistant_custom_component.common import MockConfigEntry
from wftnp import ClientState, Endpoint

from custom_components.wahoo_fitness.config_flow import probe
from custom_components.wahoo_fitness.const import DOMAIN
from tests.support.proxy import ReadOnlyProxy

pytestmark = pytest.mark.hardware


async def until(predicate, seconds=20):
    async with asyncio.timeout(seconds):
        while not predicate():  # noqa: ASYNC110 -- bounded polling observes HA and transport together
            await asyncio.sleep(0.05)


async def test_live_entities_and_recovery(hass, equipment, record_property, socket_enabled):
    pytest_socket.socket_allow_hosts(["127.0.0.1", equipment["host"]])
    async with ReadOnlyProxy(Endpoint(equipment["host"], equipment.get("port", 36866))) as proxy:
        device = await probe(proxy.endpoint.host, proxy.endpoint.port)
        entry = MockConfigEntry(
            domain=DOMAIN,
            title=equipment["name"],
            unique_id=device.serial,
            data={"host": proxy.endpoint.host, "port": proxy.endpoint.port},
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        coordinator = entry.runtime_data
        try:
            await until(lambda: all(metric in coordinator.data for metric in device.metrics))
            await hass.async_block_till_done()
            states = hass.states.async_all("sensor")
            assert len(states) == len(device.metrics)
            assert all(state.state not in ("unknown", "unavailable") for state in states)
            received = 0

            def updated():
                nonlocal received
                received += 1

            remove = coordinator.async_add_listener(updated)
            try:
                await asyncio.sleep(10)
                assert received >= 5
                for _ in range(3):
                    generation = coordinator.client.connection_id
                    proxy.interrupt()
                    await until(lambda: not coordinator.connected)
                    await hass.async_block_till_done()
                    assert all(state.state == "unavailable" for state in hass.states.async_all("sensor"))
                    await until(
                        lambda generation=generation: (
                            coordinator.client.connection_id > generation
                            and coordinator.connected
                            and all(metric in coordinator.data for metric in device.metrics)
                        )
                    )
                    await hass.async_block_till_done()
                    assert all(
                        state.state not in ("unknown", "unavailable")
                        for state in hass.states.async_all("sensor")
                    )
            finally:
                remove()
            record_property("profile", device.profile)
            record_property("metrics", ",".join(device.metrics))
            record_property("notifications", received)
            record_property("reconnections", 3)
        finally:
            assert await hass.config_entries.async_unload(entry.entry_id)
            assert coordinator.client.state == ClientState.STOPPED
        assert not proxy.errors
        assert all(opcode in (1, 2, 3, 5) for opcode, _ in proxy.requests)
