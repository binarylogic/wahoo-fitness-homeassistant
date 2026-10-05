# Protocol scope

WFTNP transports GATT operations over TCP. The `wftnp` dependency owns framing, response correlation, timeouts, disconnects, subscription delivery, and reconnect policy. This integration reads Device Information and Fitness Machine Feature and subscribes to either Indoor Bike Data (0x2AD2) or Treadmill Data (0x2ACD). No control-point operation is used.

The pure FTMS decoder follows the Bluetooth SIG [Fitness Machine Service](https://www.bluetooth.com/specifications/specs/fitness-machine-service-1-0-1/) and the [GATT Specification Supplement](https://www.bluetooth.com/specifications/gss/), reviewed against the supplement dated 2026-09-09. The SIG also publishes [machine-readable characteristic definitions](https://bitbucket.org/bluetooth-SIG/public/src/main/gss/).

Flags and numeric fields are little endian. Speed is 0.01 km/h; cadence is 0.5 rpm; power is signed watts; total distance is a 24-bit metre count; incline is signed 0.1 percent. The More Data flag means instantaneous speed is absent in that packet. It does not permit assuming absent optional values are zero. Each present value receives its own freshness timestamp.

Unavailable sentinels are applied only where defined: treadmill incline and power use 0x7FFF; total energy uses 0xFFFF. A positive bike power value of 32767 is not globally reinterpreted as unavailable. Optional fields that have no HA sensor are still consumed in order so subsequent fields remain aligned. Truncated packets, reserved flags, and unexpected trailing bytes are rejected atomically.

Two optional layouts deserve explicit version context: the 2026-09-09 supplement defines bike Resistance Level as uint8 and treadmill Pace/Average Pace as uint16. The decoder consumes these layouts but does not expose those fields. Older implementations may use different widths; there is no guessing based on packet length. Neither validated Wahoo device advertises those fields. Support for a differing device layout requires protocol evidence and a regression fixture before being claimed.

Device capabilities select sensors; live packets provide values. The initial bike advertises cadence/power (feature bits 0x4002), and the treadmill advertises distance/incline (0x000C). Both supply instantaneous speed. Vendor-specific characteristics, Cycling Power and Running Speed and Cadence profiles are not decoded. This is a focused telemetry integration, not a claim to implement all Bluetooth fitness profiles.
