# Changelog

All notable changes to this project will be documented in this file.

## [0.1.1] - 2026-08-19

### Fixed
- **Breaking change body parsing** — Detects `BREAKING CHANGE:` in commit body
- **False positive fix** — `fix: handle breaking news API` no longer flagged as breaking
- **Packaging** — Added `pyproject.toml` with `[project.scripts]` entrypoint
- **Test coverage** — Added `pytest-cov` with 80% minimum threshold

## [0.1.0] - 2026-08-19

### Added
- Initial release
- Zero-dependency CLI (Python 3.9+)
- Conventional Commits parsing (feat, fix, docs, chore, refactor, etc.)
- Multiple output formats (Markdown, plain text, JSON)
- Tag range filtering (--since, --until, --path, --scope-filter)
- Breaking change detection (! marker)
- Config file support (commitlog.json)
