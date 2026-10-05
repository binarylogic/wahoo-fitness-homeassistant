"""Read-only Wahoo Fitness integration."""

import asyncio

from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from wftnp import Endpoint, WftnpClient, WftnpError

from .coordinator import WahooConfigEntry, WahooCoordinator
from .device import UnsupportedDevice, inspect_device

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: WahooConfigEntry) -> bool:
    client = WftnpClient(Endpoint(entry.data[CONF_HOST], entry.data[CONF_PORT]))
    coordinator = None
    try:
        async with asyncio.timeout(30):
            await client.start()
            await client.wait_ready(timeout=10)
            device = await inspect_device(client)
            if device.serial != entry.unique_id:
                raise UnsupportedDevice(
                    "The endpoint now belongs to a different device; reconfigure the entry"
                )
            coordinator = WahooCoordinator(hass, entry, client, device)
            await coordinator.start()
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException as err:
        if coordinator is not None:
            await coordinator.async_shutdown()
        else:
            await client.stop()
        if isinstance(err, UnsupportedDevice):
            raise ConfigEntryError(str(err)) from err
        if isinstance(err, (WftnpError, TimeoutError, OSError)):
            raise ConfigEntryNotReady("Unable to connect to Wahoo equipment") from err
        raise

    async def stop(_event: Event) -> None:
        await coordinator.async_shutdown()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WahooConfigEntry) -> bool:
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_shutdown()
        return True
    return False
