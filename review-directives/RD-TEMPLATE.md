# RD Template — Review Directive (`_directives/RD/RD-NNN.md`)

An RD is a final, evidence-bearing review record. It never patches canon: a
`changes-requested` verdict routes remediation through a new PD→DD→VD→ED lifecycle.

```packet-spec
{"packet":"RD","required":{"id":"RD-[0-9]{3}","status":"settled","created":"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z","author":"\\S+","kind":"(code-review|intent-drift)","reviews":"ED-[0-9]{3}(,\\s*ED-[0-9]{3})*","verdict":"(pass|changes-requested)"}}
```

Required evidence is prose below the frontmatter: exact paths/packet ids, observed facts,
and, for changes requested, the new directive route. The gate checks shape and that reviewed
ED ids exist in registry history; review truth remains human-audited.
