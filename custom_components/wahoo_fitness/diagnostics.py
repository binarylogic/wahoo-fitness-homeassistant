"""Useful diagnostics without serial numbers, addresses or workout readings."""

from homeassistant.core import HomeAssistant

from .coordinator import WahooConfigEntry


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: WahooConfigEntry) -> dict:
    coordinator = entry.runtime_data
    return {
        "profile": coordinator.device.profile,
        "feature_bits": coordinator.device.feature_bits,
        "firmware": coordinator.device.firmware,
        "connection_state": coordinator.client.state,
        "connection_generation": coordinator.client.connection_id,
        "subscription_closed": coordinator.subscription.closed if coordinator.subscription else None,
        "advertised_metrics": list(coordinator.device.metrics),
        "fresh_metrics": list(coordinator.data),
    }
