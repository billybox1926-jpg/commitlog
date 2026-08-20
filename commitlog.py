#!/usr/bin/env python3
"""commitlog - local release-note generator.

Reads conventional commits from a repo and generates release notes,
changelog entries, or JSON metadata.
Zero-dependency, local-only CLI tool.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__version__ = "0.1.1"

CONVENTIONAL_COMMIT_PATTERN = re.compile(r"^(\w+)(\(([^)]+)\))?!?:\s+(.+)$")

TYPE_LABELS = {
    "feat": "Features",
    "fix": "Bug Fixes",
    "docs": "Documentation",
    "style": "Other",
    "refactor": "Other",
    "perf": "Other",
    "test": "Other",
    "build": "Other",
    "ci": "Other",
    "chore": "Other",
}

# Types that get their own section
SPECIAL_TYPES = {"feat", "fix", "docs"}

# Breaking change patterns
BREAKING_MARKER_PATTERN = re.compile(r"^(\w+)(\(([^)]+)\))?!:")
BREAKING_CHANGE_PATTERN = re.compile(r"BREAKING[- ]CHANGE\s*:", re.IGNORECASE)


def run_git(args: list[str], cwd: str | None = None) -> str:
    """Run a git command and return stdout."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=cwd,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running git {' '.join(args)}: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: git not found. Please install git.", file=sys.stderr)
        sys.exit(1)


def get_commits(
    since: str | None = None,
    until: str | None = None,
    path: str | None = None,
    include_body: bool = False,
) -> list[dict[str, Any]]:
    """Get commits from git log."""
    if include_body:
        # Use -z for null-separated commits, include body (%B)
        format_str = "%H%x09%s%x09%an%x09%ad%x09%B"
        args = ["log", "-z", f"--pretty=format:{format_str}", "--date=short"]
    else:
        format_str = "%H%x09%s%x09%an%x09%ad"
        args = ["log", f"--pretty=format:{format_str}", "--date=short"]

    if since:
        if until:
            args.append(f"{since}..{until}")
        else:
            args.append(f"{since}..HEAD")
    elif until:
        args.append(f"{until}")

    if path:
        args.extend(["--", path])

    output = run_git(args)
    if not output:
        return []

    commits = []
    if include_body:
        # Split by null byte for commits
        commit_blocks = output.split("\x00")
    else:
        commit_blocks = output.split("\n")

    for block in commit_blocks:
        if not block:
            continue
        parts = block.split("\t")
        if len(parts) >= 4:
            commit_hash, subject, author, date = parts[0], parts[1], parts[2], parts[3]
            # Body is everything after the 4th field (joined back with tabs)
            body = "\t".join(parts[4:]) if len(parts) > 4 else ""
            commits.append(
                {
                    "hash": commit_hash,
                    "short_hash": commit_hash[:7],
                    "subject": subject,
                    "author": author,
                    "date": date,
                    "body": body,
                }
            )

    return commits


def parse_conventional_commit(subject: str, body: str = "") -> dict[str, Any] | None:
    """Parse a conventional commit subject line and body."""
    match = CONVENTIONAL_COMMIT_PATTERN.match(subject)
    if not match:
        return None

    commit_type = match.group(1)
    scope = match.group(3)
    description = match.group(4)

    # Check for breaking change markers:
    # 1. ! marker in subject (e.g., feat!: or feat(api)!:)
    # 2. BREAKING CHANGE: in body
    is_breaking = BREAKING_MARKER_PATTERN.match(subject) is not None
    if not is_breaking and body:
        is_breaking = BREAKING_CHANGE_PATTERN.search(body) is not None

    return {
        "type": commit_type,
        "scope": scope,
        "description": description,
        "is_breaking": is_breaking,
    }


def classify_commits(commits: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Classify commits into sections."""
    sections: dict[str, list[dict[str, Any]]] = {
        "features": [],
        "fixes": [],
        "docs": [],
        "other": [],
    }

    for commit in commits:
        parsed = parse_conventional_commit(commit["subject"], commit.get("body", ""))
        if not parsed:
            sections["other"].append(commit)
            continue

        commit.update(parsed)

        if parsed["type"] == "feat":
            sections["features"].append(commit)
        elif parsed["type"] == "fix":
            sections["fixes"].append(commit)
        elif parsed["type"] == "docs":
            sections["docs"].append(commit)
        else:
            sections["other"].append(commit)

    # Remove empty sections
    return {k: v for k, v in sections.items() if v}


def generate_markdown(
    sections: dict[str, list[dict[str, Any]]],
    version: str = "Unreleased",
    date: str | None = None,
    repo_url: str | None = None,
) -> str:
    """Generate Markdown changelog."""
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = [f"## {version} ({date})", ""]

    section_titles = {
        "features": "Features",
        "fixes": "Bug Fixes",
        "docs": "Documentation",
        "other": "Other",
        "all": "Changes",
    }

    for section_key, title in section_titles.items():
        commits = sections.get(section_key, [])
        if not commits:
            continue

        lines.append(f"### {title}")
        lines.append("")

        for commit in commits:
            scope = commit.get("scope")
            scope_str = f"**{scope}** " if scope else ""
            breaking = " [BREAKING]" if commit.get("is_breaking") else ""

            if repo_url:
                link = f"([{commit['short_hash']}]({repo_url}/commit/{commit['hash']}))"
            else:
                link = f"({commit['short_hash']})"

            lines.append(f"- {scope_str}{commit['description']}{breaking} {link}")

        lines.append("")

    return "\n".join(lines)


def generate_text(
    sections: dict[str, list[dict[str, Any]]],
    version: str = "Unreleased",
    date: str | None = None,
) -> str:
    """Generate plain text release notes."""
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = [f"{version} ({date})", "=" * 40, ""]

    section_titles = {
        "features": "Features",
        "fixes": "Bug Fixes",
        "docs": "Documentation",
        "other": "Other",
        "all": "Changes",
    }

    for section_key, title in section_titles.items():
        commits = sections.get(section_key, [])
        if not commits:
            continue

        lines.append(f"{title}:")
        lines.append("-" * 20)

        for commit in commits:
            scope = commit.get("scope")
            scope_str = f"[{scope}] " if scope else ""
            breaking = " [BREAKING]" if commit.get("is_breaking") else ""
            entry = f"  - {scope_str}{commit['description']}{breaking}"
            entry += f" ({commit['short_hash']})"
            lines.append(entry)

        lines.append("")

    return "\n".join(lines)


def generate_json(
    sections: dict[str, list[dict[str, Any]]],
    version: str = "Unreleased",
    date: str | None = None,
) -> str:
    """Generate JSON output."""
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    output = {
        "version": version,
        "date": date,
        "sections": {},
    }

    for section_key, commits in sections.items():
        output["sections"][section_key] = [
            {
                "scope": c.get("scope"),
                "description": c["description"],
                "hash": c["hash"],
                "short_hash": c["short_hash"],
                "author": c["author"],
                "date": c["date"],
                "is_breaking": c.get("is_breaking", False),
            }
            for c in commits
        ]

    return json.dumps(output, indent=2)


def load_config(path: str = "commitlog.json") -> dict[str, Any]:
    """Load commitlog.json config file."""
    config_path = Path(path)
    if not config_path.exists():
        return {}

    try:
        with config_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="commitlog - Local release-note generator"
    )
    parser.add_argument(
        "--version", action="version", version=f"commitlog {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="command to execute")

    generate_parser = subparsers.add_parser("generate", help="generate release notes")
    generate_parser.add_argument(
        "--since",
        default=None,
        help="start from tag or commit (e.g., v0.1.0)",
    )
    generate_parser.add_argument(
        "--until",
        default=None,
        help="end at tag or commit (optional)",
    )
    generate_parser.add_argument(
        "--path",
        default=None,
        help="filter by directory path",
    )
    generate_parser.add_argument(
        "--format",
        choices=["markdown", "text", "json"],
        default="markdown",
        help="output format (default: markdown)",
    )
    generate_parser.add_argument(
        "--output",
        default=None,
        help="write to file instead of stdout",
    )
    generate_parser.add_argument(
        "--scope-filter",
        default=None,
        help="only include commits with given scope",
    )
    generate_parser.add_argument(
        "--no-group",
        action="store_true",
        help="don't group by type, list chronologically",
    )
    generate_parser.add_argument(
        "--include-body",
        action="store_true",
        help="include full commit body",
    )

    subparsers.add_parser("init", help="create commitlog.json config")

    args = parser.parse_args()

    if args.command == "generate":
        generate_command(args)
    elif args.command == "init":
        init_command(args)
    else:
        parser.print_help()
        sys.exit(1)


def generate_command(args: argparse.Namespace) -> None:
    """Run the generate command."""
    config = load_config()

    # Merge config with CLI args (CLI takes precedence)
    since = args.since or config.get("default_since")
    until = args.until
    format_type = args.format or config.get("default_format", "markdown")
    path = args.path
    scope_filter = args.scope_filter
    no_group = args.no_group
    include_body = args.include_body

    # Handle "last_tag" as since
    if since == "last_tag":
        since = get_last_tag()

    commits = get_commits(
        since=since, until=until, path=path, include_body=include_body
    )

    if scope_filter:
        commits = [
            c
            for c in commits
            if parse_conventional_commit(c["subject"], c.get("body", ""))
            and parse_conventional_commit(c["subject"], c.get("body", "")).get("scope")
            == scope_filter
        ]

    sections = classify_commits(commits)

    if no_group:
        # Flatten all commits into a single list
        all_commits = []
        for section_commits in sections.values():
            all_commits.extend(section_commits)
        # Sort by date
        all_commits.sort(key=lambda c: c["date"])
        sections = {"all": all_commits} if all_commits else {}

    version = args.until or "Unreleased"
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if format_type == "markdown":
        output = generate_markdown(sections, version, date)
    elif format_type == "text":
        output = generate_text(sections, version, date)
    elif format_type == "json":
        output = generate_json(sections, version, date)
    else:
        print(f"Error: Unknown format {format_type}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Output written to {args.output}")
    else:
        print(output)


def init_command(args: argparse.Namespace) -> None:
    """Run the init command."""
    config = {
        "grouping": True,
        "default_since": "last_tag",
        "default_format": "markdown",
        "ignored_scopes": ["chore"],
    }

    config_path = Path("commitlog.json")
    if config_path.exists():
        print("commitlog.json already exists. Overwrite? [y/N]")
        response = input().strip().lower()
        if response != "y":
            print("Aborted.")
            return

    with config_path.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    print("Created commitlog.json")


def get_last_tag() -> str | None:
    """Get the most recent tag."""
    try:
        output = run_git(["describe", "--tags", "--abbrev=0"])
        return output
    except SystemExit:
        return None


if __name__ == "__main__":
    main()
