"""Pure FTMS notification decoding. See docs/protocol.md for the wire definitions."""

from dataclasses import dataclass
from enum import StrEnum


class Profile(StrEnum):
    BIKE = "bike"
    TREADMILL = "treadmill"


class Metric(StrEnum):
    SPEED = "speed"
    CADENCE = "cadence"
    POWER = "power"
    DISTANCE = "distance"
    INCLINE = "incline"
    HEART_RATE = "heart_rate"
    ELAPSED_TIME = "elapsed_time"
    ENERGY = "energy"


@dataclass(frozen=True, slots=True)
class Measurement:
    metric: Metric
    value: float | None


@dataclass(frozen=True, slots=True)
class Packet:
    measurements: tuple[Measurement, ...]
    more_data: bool


class DecodeError(ValueError):
    """A notification cannot be decoded without guessing its layout."""


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0
        self.measurements: list[Measurement] = []

    def number(self, size: int = 2, *, signed: bool = False) -> int:
        end = self.offset + size
        if end > len(self.data):
            raise DecodeError("Truncated FTMS notification")
        value = int.from_bytes(self.data[self.offset : end], "little", signed=signed)
        self.offset = end
        return value

    def metric(
        self,
        metric: Metric,
        size: int = 2,
        *,
        signed: bool = False,
        divisor: float = 1,
        unavailable: int | None = None,
    ) -> None:
        raw = self.number(size, signed=signed)
        value = None if raw == unavailable else raw / divisor
        self.measurements.append(Measurement(metric, value))

    def energy(self) -> None:
        self.metric(Metric.ENERGY, unavailable=0xFFFF)
        self.number(2)  # Energy/hour, not exposed.
        self.number(1)  # Energy/minute, not exposed.


def decode(profile: Profile, data: bytes) -> Packet:
    """Return only fields present in this packet; explicit unavailable values are None."""
    reader = _Reader(data)
    flags = reader.number()
    if flags & 0xE000:
        raise DecodeError("Unsupported reserved FTMS flags")
    if not flags & 1:
        reader.metric(Metric.SPEED, divisor=100)
    if flags & (1 << 1):
        reader.number()  # Average speed.
    if profile == Profile.BIKE:
        _bike(reader, flags)
    else:
        _treadmill(reader, flags)
    if reader.offset != len(data):
        raise DecodeError("Unexpected trailing FTMS bytes")
    return Packet(tuple(reader.measurements), bool(flags & 1))


def _bike(reader: _Reader, flags: int) -> None:
    if flags & (1 << 2):
        reader.metric(Metric.CADENCE, divisor=2)
    if flags & (1 << 3):
        reader.number()  # Average cadence.
    if flags & (1 << 4):
        reader.metric(Metric.DISTANCE, 3)
    if flags & (1 << 5):
        reader.number(1)  # Resistance level (GSS 2026-09-09); not exposed.
    if flags & (1 << 6):
        reader.metric(Metric.POWER, signed=True)
    if flags & (1 << 7):
        reader.number(signed=True)  # Average power.
    if flags & (1 << 8):
        reader.energy()
    if flags & (1 << 9):
        reader.metric(Metric.HEART_RATE, 1)
    if flags & (1 << 10):
        reader.number(1)  # Metabolic equivalent.
    if flags & (1 << 11):
        reader.metric(Metric.ELAPSED_TIME)
    if flags & (1 << 12):
        reader.number()  # Remaining time.


def _treadmill(reader: _Reader, flags: int) -> None:
    if flags & (1 << 2):
        reader.metric(Metric.DISTANCE, 3)
    if flags & (1 << 3):
        reader.metric(Metric.INCLINE, signed=True, divisor=10, unavailable=0x7FFF)
        reader.number(signed=True)  # Ramp angle; may itself be unavailable.
    if flags & (1 << 4):
        reader.number()  # Positive elevation gain.
        reader.number()  # Negative elevation gain.
    if flags & (1 << 5):
        reader.number()  # Pace in seconds per 500 m (GSS 2026-09-09).
    if flags & (1 << 6):
        reader.number()  # Average pace.
    if flags & (1 << 7):
        reader.energy()
    if flags & (1 << 8):
        reader.metric(Metric.HEART_RATE, 1)
    if flags & (1 << 9):
        reader.number(1)  # Metabolic equivalent.
    if flags & (1 << 10):
        reader.metric(Metric.ELAPSED_TIME)
    if flags & (1 << 11):
        reader.number()  # Remaining time.
    if flags & (1 << 12):
        reader.number(signed=True)  # Force on belt.
        reader.metric(Metric.POWER, signed=True, unavailable=0x7FFF)


def supported_metrics(profile: Profile, feature_bits: int) -> tuple[Metric, ...]:
    """Select entities from advertised data features, never from control capabilities."""
    features = {
        Metric.DISTANCE: 2,
        Metric.ENERGY: 9,
        Metric.HEART_RATE: 10,
        Metric.ELAPSED_TIME: 12,
        Metric.POWER: 14 if profile == Profile.BIKE else 15,
    }
    if profile == Profile.BIKE:
        features[Metric.CADENCE] = 1
    else:
        features[Metric.INCLINE] = 3
    return (Metric.SPEED, *(metric for metric, bit in features.items() if feature_bits & (1 << bit)))
