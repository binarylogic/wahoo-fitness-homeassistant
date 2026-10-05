"""Wire examples include real idle captures and synthetic nonzero values."""

import struct

import pytest

from custom_components.wahoo_fitness.ftms import DecodeError, Metric, Profile, decode, supported_metrics


def values(profile, data):
    return {item.metric: item.value for item in decode(profile, data).measurements}


@pytest.mark.parametrize(
    ("profile", "hex_data", "expected"),
    [
        (Profile.BIKE, "4400000000000000", {Metric.SPEED: 0, Metric.CADENCE: 0, Metric.POWER: 0}),
        (
            Profile.TREADMILL,
            "0c0000000000000000ff7f",
            {Metric.SPEED: 0, Metric.DISTANCE: 0, Metric.INCLINE: 0},
        ),
        (Profile.BIKE, "4400b80bb500fa00", {Metric.SPEED: 30, Metric.CADENCE: 90.5, Metric.POWER: 250}),
        (
            Profile.TREADMILL,
            "0c00e803393000ecffff7f",
            {Metric.SPEED: 10, Metric.DISTANCE: 12345, Metric.INCLINE: -2},
        ),
        (Profile.TREADMILL, "0800e803ff7fff7f", {Metric.SPEED: 10, Metric.INCLINE: None}),
    ],
)
def test_examples(profile, hex_data, expected):
    assert values(profile, bytes.fromhex(hex_data)) == expected


def test_partial_packet_and_signed_power():
    packet = decode(Profile.BIKE, struct.pack("<Hh", 0x41, -12))
    assert packet.more_data
    assert [(item.metric, item.value) for item in packet.measurements] == [(Metric.POWER, -12)]


@pytest.mark.parametrize("profile", list(Profile))
def test_energy_unavailable(profile):
    bit = 8 if profile == Profile.BIKE else 7
    result = values(profile, struct.pack("<HHHB", (1 << bit) | 1, 65535, 65535, 255))
    assert result == {Metric.ENERGY: None}


@pytest.mark.parametrize(
    "profile,payload", [(Profile.BIKE, "4400b80bb500fa00"), (Profile.TREADMILL, "0c00e803393000ecffff7f")]
)
def test_every_truncation_rejected(profile, payload):
    data = bytes.fromhex(payload)
    for end in range(len(data)):
        with pytest.raises(DecodeError):
            decode(profile, data[:end])
    with pytest.raises(DecodeError):
        decode(profile, data + b"\x00")


@pytest.mark.parametrize("profile", list(Profile))
def test_reserved_flags(profile):
    with pytest.raises(DecodeError):
        decode(profile, b"\x01\x80")


def test_features():
    assert set(supported_metrics(Profile.BIKE, 0x4002)) == {Metric.SPEED, Metric.CADENCE, Metric.POWER}
    assert set(supported_metrics(Profile.TREADMILL, 0x0C)) == {Metric.SPEED, Metric.DISTANCE, Metric.INCLINE}
    assert supported_metrics(Profile.BIKE, 0) == (Metric.SPEED,)


def test_all_bike_fields_in_order():
    # Current GSS: resistance uint8; unexposed optional fields must still be consumed.
    data = struct.pack("<HHHHH", 0x1FFE, 3025, 3000, 181, 180) + (123456).to_bytes(3, "little")
    data += struct.pack("<BhhHHBBBHH", 7, 250, 240, 100, 200, 3, 145, 12, 600, 1200)
    assert values(Profile.BIKE, data) == {
        Metric.SPEED: 30.25,
        Metric.CADENCE: 90.5,
        Metric.DISTANCE: 123456,
        Metric.POWER: 250,
        Metric.ENERGY: 100,
        Metric.HEART_RATE: 145,
        Metric.ELAPSED_TIME: 600,
    }


def test_all_treadmill_fields_in_order():
    data = struct.pack("<HHH", 0x1FFE, 1000, 900) + (12345).to_bytes(3, "little")
    data += struct.pack(
        "<hhHHHHHHBBBHHhh", 15, 32767, 20, 10, 180, 200, 100, 200, 3, 145, 12, 600, 1200, 32767, 32767
    )
    assert values(Profile.TREADMILL, data) == {
        Metric.SPEED: 10,
        Metric.DISTANCE: 12345,
        Metric.INCLINE: 1.5,
        Metric.ENERGY: 100,
        Metric.HEART_RATE: 145,
        Metric.ELAPSED_TIME: 600,
        Metric.POWER: None,
    }
