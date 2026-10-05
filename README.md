# Wahoo Fitness for Home Assistant

Live, local, read-only metrics from Wi-Fi enabled Wahoo fitness equipment. No Wahoo account or cloud connection is required.

| Equipment validated | Sensors |
| --- | --- |
| KICKR BIKE (Wi-Fi model) | Speed, cadence, power |
| KICKR RUN | Speed, distance, incline |

Other WFTNP devices with the FTMS Indoor Bike Data or Treadmill Data characteristic may work, but have not been hardware validated. Bluetooth-only equipment and ELEMNT computers are outside this integration's scope.

## Installation

Requires Home Assistant **2026.9.4 or newer**. In HACS, add `https://github.com/binarylogic/wahoo-fitness-homeassistant` as a custom **Integration** repository, then download **Wahoo Fitness** and restart Home Assistant. Add the discovered equipment under **Settings → Devices & services**, or add **Wahoo Fitness** manually using its local IP address and port (normally `36866`). Equipment must be awake and reachable from Home Assistant.

Discovery uses Home Assistant's existing Zeroconf service. Device serial numbers provide stable identity when addresses change. Manual entries can be reconfigured to a new address; a different device cannot silently replace an existing entry.

The integration subscribes to telemetry. It never requests equipment control or sends speed, incline, resistance, or workout commands. Keep using your training and media apps independently. An active ROUVY workout running alongside this integration has not yet been validated.

## Reading behavior

- Sensors are selected from the equipment's advertised FTMS capabilities. Unsupported metrics are not invented or estimated.
- Units are km/h, rpm, W, m, %, bpm, seconds, and kcal as applicable. Home Assistant can convert supported units for display.
- Zero is a measured value. Explicit protocol “not available” values become `unknown`.
- A disconnect immediately makes readings `unavailable`. Each field also expires independently after 15 seconds without an update (checked once per second). No previous workout readings are restored after a restart or disconnect.
- Partial notifications update only their included fields. Malformed notifications cannot refresh old values.
- `wftnp` reconnects and restores subscriptions. A terminal subscription failure reloads the entry once; Home Assistant handles subsequent setup retries.
- Distance, elapsed time, and energy are equipment-provided workout counters. They have no long-term statistics state class because workout/reset semantics have not been established across devices. This integration does not record workout sessions or calculate missing totals.

## Architecture

`wftnp` is the standalone [WFTNP transport library](https://github.com/binarylogic/py-wftnp). This repository depends on its published release, not a sibling checkout.

```
custom_components/wahoo_fitness/
  __init__.py       setup, unload, shutdown
  config_flow.py    discovery, manual setup, identity validation
  device.py         read-only identity and capability inspection
  ftms.py           pure packet decoding, units, unavailable sentinels
  coordinator.py    push updates, generation boundaries, per-field freshness
  sensor.py         Home Assistant entity projection
  diagnostics.py   diagnostics without addresses, serials or readings
  const.py         protocol UUIDs and integration constants
```

There is no device-control API, second connection supervisor, cloud service, or dashboard/media policy here. See [protocol notes](docs/protocol.md).

## Development and validation

Install [uv](https://docs.astral.sh/uv/) and [Task](https://taskfile.dev/), then run `task install` and `task check`. The locked test environment uses the same Home Assistant version as the initial deployment. CI runs lint, formatting, type checking, HA/decoder tests, Hassfest, and HACS validation. Releases use Release Please.

Ordinary tests never contact equipment. For the **single serial hardware lane**, create the ignored `.hardware.toml`:

```toml
[[devices]]
name = "Bike"
host = "192.0.2.10"

[[devices]]
name = "Treadmill"
host = "192.0.2.11"
```

Run `task test:hardware`. Do not use xdist. The test creates actual HA sensor entities, checks streaming, interrupts its own socket three times per device, verifies recovery, then unloads. A forwarding proxy rejects every equipment-control write. Reports stay in ignored `.artifacts/`.

Initial hardware validation passed on a KICKR BIKE and KICKR RUN while idle. Nonzero values and optional fields are covered by synthetic wire fixtures; an actual moving workout and simultaneous training-app session remain explicit manual validation steps. Passing idle tests is not a claim that those scenarios have been tested.
