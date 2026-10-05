"""One opt-in, serial hardware lane; never contacts devices during ordinary tests."""

import tomllib
from pathlib import Path

import pytest


def pytest_generate_tests(metafunc):
    if "equipment" not in metafunc.fixturenames:
        return
    if not metafunc.config.getoption("--hardware") or getattr(metafunc.config.option, "numprocesses", None):
        raise pytest.UsageError("Hardware tests require --hardware and a single serial lane")
    try:
        equipment = tomllib.loads(Path(metafunc.config.getoption("--hardware-config")).read_text())["devices"]
        if not equipment:
            raise ValueError("No devices configured")
    except (OSError, ValueError, KeyError) as err:
        raise pytest.UsageError("Create .hardware.toml using the documented example") from err
    metafunc.parametrize("equipment", equipment, ids=[item["name"] for item in equipment])
