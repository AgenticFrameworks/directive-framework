# Canon divergence record — portable/ed/canon/

Install target: `dev/directive-framework/portable/ed/canon/DIVERGENCE.md` (ED-043 F-step).

Known, adjudicated divergences between the portable canon snapshot (taken 2026-07-02) and
the live canon in `dev/directive-framework/execute/`. `detect-drift.py` (ED-043) downgrades
a `canon-divergence` finding from ERROR to INFO if and only if the diverged file is named in
this record — an entry here means "we know, it is owed a refresh", not "it is fine forever".
Remove a row when a snapshot-refresh directive re-syncs that file.

| File | Diverged since | Status |
|---|---|---|
| CHECKLIST.md | 2026-07-02 snapshot | live canon evolved after the snapshot (incident-earned checklist growth); refresh owed |
| CROSS-VET.md | 2026-07-02 snapshot | live canon evolved after the snapshot; refresh owed |
| ED-TEMPLATE.md | 2026-07-02 snapshot | live canon evolved after the snapshot (REOPENED-era template changes); refresh owed |
| USAGE.md | 2026-07-02 snapshot | live canon evolved after the snapshot; refresh owed |

`LAUNCH-TEMPLATE.md` is byte-identical to live canon (probed 2026-07-09) and deliberately
has no entry. A snapshot-refresh directive covering all four rows is the follow-up ED-043
explicitly leaves out of scope (§7).

Recorded by ED-043, 2026-07-09.
