"""FTMS values projected into native Home Assistant sensors."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfLength, UnitOfPower, UnitOfSpeed, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WahooConfigEntry, WahooCoordinator
from .ftms import Metric

DESCRIPTIONS = {
    Metric.SPEED: SensorEntityDescription(
        key="speed",
        translation_key="speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Metric.CADENCE: SensorEntityDescription(
        key="cadence",
        translation_key="cadence",
        native_unit_of_measurement="rpm",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:rotate-right",
    ),
    Metric.POWER: SensorEntityDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Metric.DISTANCE: SensorEntityDescription(
        key="distance",
        translation_key="distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
    ),
    Metric.INCLINE: SensorEntityDescription(
        key="incline",
        translation_key="incline",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:slope-uphill",
    ),
    Metric.HEART_RATE: SensorEntityDescription(
        key="heart_rate",
        translation_key="heart_rate",
        native_unit_of_measurement="bpm",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:heart-pulse",
    ),
    Metric.ELAPSED_TIME: SensorEntityDescription(
        key="elapsed_time",
        translation_key="elapsed_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
    ),
    Metric.ENERGY: SensorEntityDescription(
        key="energy",
        translation_key="energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: WahooConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities(
        WahooSensor(entry.runtime_data, metric) for metric in entry.runtime_data.device.metrics
    )


class WahooSensor(CoordinatorEntity[WahooCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: WahooCoordinator, metric: Metric) -> None:
        super().__init__(coordinator)
        self.metric = metric
        self.entity_description = DESCRIPTIONS[metric]
        device = coordinator.device
        self._attr_unique_id = f"{device.serial}_{metric}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.serial)},
            name=coordinator.config_entry.title if coordinator.config_entry else device.model,
            manufacturer=device.manufacturer,
            model=device.model,
            sw_version=device.firmware,
            serial_number=device.serial,
        )

    @property
    def available(self) -> bool:
        return self.coordinator.connected and self.metric in self.coordinator.data

    @property
    def native_value(self) -> float | None:
        sample = self.coordinator.data.get(self.metric)
        return sample.value if sample is not None else None
