# Metrics moved to runtime (ED-003)

Metrics are RUNTIME state, not canon. They are derived from the per-project registry:

```
python3 execution-directives/derive-metrics.py            # writes <registry-dir>/METRICS.md
```

Canon carries no metrics, lessons, registry, or dashboards — see `RUNTIME-SPEC.md`.
The pre-ED-003 content of this file was a stale snapshot of the superseded ag-os
registry and was evicted under the clean-canon rule.
