# Wahoo Fitness Home Assistant

- Keep this integration read-only. Never request control or send equipment-control writes.
- `wftnp` owns connection/reconnect/subscription recovery; do not duplicate its transport policy.
- Keep FTMS decoding pure and separate from Home Assistant state projection.
- Missing metrics are unknown, stale or disconnected metrics unavailable, and measured zero stays zero.
- Keep device/entity identity stable across endpoint changes and restarts.
- Use `uv` and `task check`. Test HA setup, config flow, entities, recovery, freshness, and unload.
- `task test:hardware` is one explicit serial lane. Addresses and reports stay gitignored.
- Use conventional commits. Complete review, tests, and hardware validation before the initial release.
- Use Release Please for releases; release versions must match the integration manifest.
