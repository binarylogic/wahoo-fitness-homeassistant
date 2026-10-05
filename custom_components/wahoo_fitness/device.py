"""Read-only device identification and capability inspection."""

from dataclasses import dataclass
from uuid import UUID

from wftnp import CharacteristicProperties, WftnpClient

from .const import (
    BIKE_DATA,
    DEVICE_INFORMATION,
    FIRMWARE_REVISION,
    FITNESS_FEATURE,
    FITNESS_MACHINE,
    MANUFACTURER,
    MODEL_NUMBER,
    SERIAL_NUMBER,
    TREADMILL_DATA,
)
from .ftms import Metric, Profile, supported_metrics


class UnsupportedDevice(ValueError):
    """The peer lacks the required telemetry or stable device identity."""


@dataclass(frozen=True, slots=True)
class Device:
    serial: str
    manufacturer: str
    model: str
    firmware: str | None
    profile: Profile
    feature_bits: int

    @property
    def characteristic(self) -> UUID:
        return BIKE_DATA if self.profile == Profile.BIKE else TREADMILL_DATA

    @property
    def metrics(self) -> tuple[Metric, ...]:
        return supported_metrics(self.profile, self.feature_bits)


async def inspect_device(client: WftnpClient) -> Device:
    services = {service.uuid for service in await client.discover_services()}
    if not {FITNESS_MACHINE, DEVICE_INFORMATION} <= services:
        raise UnsupportedDevice("Requires FTMS and Device Information services")
    characteristics = {item.uuid: item for item in await client.discover_characteristics(FITNESS_MACHINE)}
    profiles = [
        profile
        for profile, uuid in ((Profile.BIKE, BIKE_DATA), (Profile.TREADMILL, TREADMILL_DATA))
        if uuid in characteristics and characteristics[uuid].properties & CharacteristicProperties.NOTIFY
    ]
    if len(profiles) != 1 or FITNESS_FEATURE not in characteristics:
        raise UnsupportedDevice("Requires one supported FTMS data characteristic and feature flags")
    features = await client.read_characteristic(FITNESS_FEATURE)
    if len(features) != 8:
        raise UnsupportedDevice("Invalid Fitness Machine Feature length")
    information = {
        item.uuid
        for item in await client.discover_characteristics(DEVICE_INFORMATION)
        if item.properties & CharacteristicProperties.READ
    }

    async def text(uuid: UUID) -> str | None:
        if uuid not in information:
            return None
        value = (await client.read_characteristic(uuid)).decode("utf-8", errors="replace").strip("\x00 \r\n")
        return value or None

    serial = await text(SERIAL_NUMBER)
    if serial is None:
        raise UnsupportedDevice("A stable device serial number is required")
    return Device(
        serial=serial,
        manufacturer=await text(MANUFACTURER) or "Wahoo",
        model=await text(MODEL_NUMBER) or ("Indoor bike" if profiles[0] == Profile.BIKE else "Treadmill"),
        firmware=await text(FIRMWARE_REVISION),
        profile=profiles[0],
        feature_bits=int.from_bytes(features[:4], "little"),
    )
