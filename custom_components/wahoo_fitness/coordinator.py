"""Push telemetry, with per-field freshness and transport-owned recovery."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from wftnp import ClientState, Notification, Subscription, WftnpClient

from .const import DOMAIN, STALE_SECONDS
from .device import Device
from .ftms import DecodeError, Metric, decode

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Sample:
    value: float | None
    received: float


class WahooCoordinator(DataUpdateCoordinator[dict[Metric, Sample]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: WftnpClient, device: Device) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry)
        self.client = client
        self.device = device
        self.data = {}
        self.subscription: Subscription | None = None
        self._generation = client.connection_id
        self._remove_state = client.add_state_listener(self._state_changed)
        self._remove_timer = async_track_time_interval(hass, self._expire, timedelta(seconds=1))
        self._stopped = False
        self._reload_scheduled = False

    async def start(self) -> None:
        self.subscription = await self.client.subscribe(self.device.characteristic, self._notification)

    @property
    def connected(self) -> bool:
        return (
            not self._stopped
            and self.client.state == ClientState.READY
            and self.subscription is not None
            and not self.subscription.closed
        )

    @callback
    def _state_changed(self, state: ClientState) -> None:
        if state != ClientState.READY or self._generation != self.client.connection_id:
            self.data = {}
        self._generation = self.client.connection_id
        self.async_update_listeners()

    @callback
    def _notification(self, notification: Notification) -> None:
        if self._stopped or notification.connection_id != self.client.connection_id:
            return
        if notification.characteristic != self.device.characteristic:
            return
        try:
            packet = decode(self.device.profile, notification.value)
        except DecodeError as err:
            _LOGGER.debug("Ignoring invalid %s telemetry: %s", self.device.profile, err)
            return
        now = self.hass.loop.time()
        data = dict(self.data) if self._generation == notification.connection_id else {}
        self._generation = notification.connection_id
        for measurement in packet.measurements:
            data[measurement.metric] = Sample(measurement.value, now)
        self.async_set_updated_data(data)

    @callback
    def _expire(self, _now: datetime) -> None:
        if self._stopped:
            return
        now = self.hass.loop.time()
        fresh = {
            metric: sample for metric, sample in self.data.items() if now - sample.received < STALE_SECONDS
        }
        if not self.connected:
            fresh = {}
        if fresh != self.data:
            self.async_set_updated_data(fresh)
        if self.subscription is not None and self.subscription.closed and not self._reload_scheduled:
            # A terminal subscription failure is distinct from a recoverable socket loss.
            # Re-enter HA setup once; HA owns any subsequent setup retry/backoff.
            self._reload_scheduled = True
            _LOGGER.warning("Telemetry subscription ended; reloading entry: %s", self.subscription.error)
            if self.config_entry is not None:
                self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)

    async def async_shutdown(self) -> None:
        if not self._stopped:
            self._stopped = True
            self._remove_timer()
            self._remove_state()
            await self.client.stop()
        await super().async_shutdown()


type WahooConfigEntry = ConfigEntry[WahooCoordinator]
