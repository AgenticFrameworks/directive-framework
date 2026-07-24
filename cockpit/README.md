# Directive Planner — Cockpit surface

An interactive, research-grounded **planning front door** for the Directive Framework.
You converse to converge on scope, then export **gate-passing `PD` / `DD` packets** that
drop straight into a consuming project's `_directives/planning-directives/` runtime.

It is a self-contained, client-only static web app — no backend, no network calls beyond
the Google Fonts stylesheet. All work stays in the browser; packets are produced via the
in-app export/download controls.

## Contents

| Path | Purpose |
|---|---|
| `index.html` | App entry (Vite build) |
| `assets/index-*.js` | Compiled application bundle |
| `assets/index-*.css` | Compiled styles |

This is a **built artifact**. The upstream source lives outside this repo; only the
distributable bundle is tracked here so the surface ships with the canon.

## Run it

Serve the directory over any static file server (the module bundle needs `http(s)://`,
not `file://`):

```bash
# from the repo root
python3 -m http.server 5173 --directory cockpit
# then open http://localhost:5173/
```

## Where it fits

The cockpit sits at the **front** of the five-phase pipeline
(**Planning → Design → Validation → Execution → Review**). It only produces Planning-phase
artifacts (`PD`/`DD`); every downstream gate, lifecycle, and executor contract is unchanged.
See `planning-directives/PLANNING-SPEC.md` for the packet contracts the exported artifacts
must satisfy, and the root `README.md` for the full surface list.
