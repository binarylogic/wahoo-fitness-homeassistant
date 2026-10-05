"""Integration constants and standard GATT UUIDs."""

from uuid import UUID

DOMAIN = "wahoo_fitness"
DEFAULT_PORT = 36866
STALE_SECONDS = 15.0
SERVICE_TYPE = "_wahoo-fitness-tnp._tcp.local."


def bluetooth_uuid(value: int) -> UUID:
    return UUID(f"{value:08x}-0000-1000-8000-00805f9b34fb")


FITNESS_MACHINE = bluetooth_uuid(0x1826)
DEVICE_INFORMATION = bluetooth_uuid(0x180A)
FITNESS_FEATURE = bluetooth_uuid(0x2ACC)
BIKE_DATA = bluetooth_uuid(0x2AD2)
TREADMILL_DATA = bluetooth_uuid(0x2ACD)
SERIAL_NUMBER = bluetooth_uuid(0x2A25)
MANUFACTURER = bluetooth_uuid(0x2A29)
MODEL_NUMBER = bluetooth_uuid(0x2A24)
FIRMWARE_REVISION = bluetooth_uuid(0x2A26)
