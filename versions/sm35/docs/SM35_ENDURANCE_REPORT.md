# SM35 endurance report

Separate entrypoints enforce exact 24-hour and 72-hour real-monotonic profiles.
They emit minute-scale telemetry and a content hash chain and cannot accept a
shorter requested duration. The V&V gate additionally requires bounded heartbeat
gaps, valid chain closure, and at least one recovery drill for 24 hours or two
for 72 hours.

The present session cannot remain active for either qualifying duration. Both
runs are NOT_EXECUTED; no shortened run is relabeled as endurance evidence.
