# Install directive-framework

Install this repository as a Claude Code plugin from its repository root. The plugin contains
only canon: templates, specs, gates, and tools. In each consuming project initialize separate
runtime state with `python3 <plugin-root>/tools/init-runtime.py --project <project>`; never copy
this repository's `_directives/` directory or `.env`.

Verify with `bash <plugin-root>/tools/check-canon-purity.sh` and
`python3 <plugin-root>/tools/gate-runner.py --validate-templates <plugin-root>/gates`.
