# Install

The directive-framework pi package ships from the `pi/` directory of this repo.

## From git (recommended)

```bash
pi install git:github.com/daedalusos/directive-framework
```

This clones the repo, reads `pi/package.json`, and loads the `extensions/` and
`skills/` resources. Pin a ref to lock the version:

```bash
pi install git:github.com/daedalusos/directive-framework@v1.1.0
```

Update pinned packages explicitly:

```bash
pi update --extension git:github.com/daedalusos/directive-framework
```

## Try without installing

```bash
pi -e git:github.com/daedalusos/directive-framework
```

Installs to a temporary directory for the current run only.

## From a local checkout

```bash
pi install /path/to/directive-framework/pi
# or relative to the settings file:
pi install ./pi
```

## Project-local (shared with a team)

Add to `.pi/settings.json` (committed) so the package loads for everyone who
trusts the project:

```json
{
  "packages": ["git:github.com/daedalusos/directive-framework@v1.1.0"]
}
```

Use `-l` to write project settings instead of user settings:

```bash
pi install -l git:github.com/daedalusos/directive-framework
```

## Configuration

After install, add the directives config block to `~/.pi/agent/settings.json`:

```json
{
  "directives": { "yolo": false, "autoInit": false }
}
```

Then restart pi (or `/reload`). The extension auto-loads; the `directive_*`
tools and `/directives` command become available; the
`/skill:directive-framework` skill becomes discoverable.

## Verify

```bash
/directives status
```

Prints the phase/role/registry/lanes summary for the current project. If the
runtime is not yet initialized for this project:

```bash
/directives init
```

Creates `~/.pi/agent/directives/<slug>/` with `cursor.json`, `registry.jsonl`,
and the `PD/ DD/ VD/ ED/ RD/ lanes/` directories.

## Uninstall

```bash
pi remove git:github.com/daedalusos/directive-framework
```

Runtime state under `~/.pi/agent/directives/` is not removed by uninstall — it
is per-project durable state. Remove it manually if you want a clean slate.
