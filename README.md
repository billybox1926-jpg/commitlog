# commitlog

**Local release-note generator.**

Reads conventional commits from a repo and generates release notes, changelog entries, or JSON metadata. Zero-dependency, local-only CLI tool.

## The Problem

> "What changed in this release?" without a CI server or external package.

## Quick Start

```bash
# Clone and run
git clone https://github.com/billybox1926-jpg/commitlog.git
cd commitlog

# Generate release notes since last tag
python commitlog.py generate

# Generate for a specific range
python commitlog.py generate --since v0.1.0 --until v0.2.0

# Output as JSON
python commitlog.py generate --since v0.1.0 --format json

# Write to file
python commitlog.py generate --since v0.1.0 --output CHANGELOG.md

# Create config file
python commitlog.py init
```

## Features

- **Zero dependencies** — Python 3.9+ stdlib only
- **Conventional Commits** — Parses `feat`, `fix`, `docs`, `chore`, `refactor`, etc.
- **Scoped commits** — `feat(api): add endpoint` grouped by scope
- **Multiple formats** — Markdown, plain text, JSON
- **Flexible filtering** — By tag range, path, or scope
- **Breaking changes** — Detects `!` marker and `BREAKING CHANGE:` in body
- **Config file** — `commitlog.json` for default settings

## CLI Usage

```
python commitlog.py generate [--since TAG] [--until TAG] [--path DIR]
                              [--format markdown|text|json] [--output PATH]
                              [--scope-filter SCOPE] [--no-group] [--include-body]

python commitlog.py init
```

## Configuration

Create `commitlog.json`:

```json
{
  "grouping": true,
  "default_since": "last_tag",
  "default_format": "markdown",
  "ignored_scopes": ["chore"]
}
```

## Output Example

```markdown
## v0.2.0 (2026-08-19)

### Features
- **api** add new endpoint ([abc1234](https://github.com/user/repo/commit/abc1234))
- add user profile page ([def5678](...))

### Bug Fixes
- fix login redirect ([123abcd](...))

### Documentation
- update README ([456efgh](...))

### Other
- **ci** add pytest workflow ([789ijkl](...))
```

## Supported Commit Types

| Type | Section |
|------|---------|
| `feat` | Features |
| `fix` | Bug Fixes |
| `docs` | Documentation |
| `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore` | Other |

## License

MIT
