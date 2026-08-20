#!/usr/bin/env python3
"""Tests for commitlog v0.1.1."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

import commitlog


class TestRunGit(unittest.TestCase):
    """Test git command execution."""

    def test_run_git_success(self):
        """Test successful git command."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="output\n", stderr="", returncode=0)
            result = commitlog.run_git(["status"])
            self.assertEqual(result, "output")

    def test_run_git_failure(self):
        """Test git command failure exits."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "git", stderr="error")
            with self.assertRaises(SystemExit):
                commitlog.run_git(["status"])

    def test_run_git_not_found(self):
        """Test git not found exits."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            with self.assertRaises(SystemExit):
                commitlog.run_git(["status"])


class TestGetCommits(unittest.TestCase):
    """Test git commit retrieval."""

    def test_get_commits_basic(self):
        """Test basic commit retrieval."""
        with patch("commitlog.run_git") as mock_git:
            mock_git.return_value = "abc123\tfeat: add feature\tTest User\t2026-01-01"
            commits = commitlog.get_commits()
            self.assertEqual(len(commits), 1)
            self.assertEqual(commits[0]["hash"], "abc123")
            self.assertEqual(commits[0]["subject"], "feat: add feature")

    def test_get_commits_with_since(self):
        """Test commit retrieval with since parameter."""
        with patch("commitlog.run_git") as mock_git:
            mock_git.return_value = "abc123\tfeat: add feature\tTest User\t2026-01-01"
            commits = commitlog.get_commits(since="v0.1.0")
            mock_git.assert_called_once()
            call_args = mock_git.call_args[0][0]
            self.assertIn("v0.1.0..HEAD", call_args)

    def test_get_commits_with_until(self):
        """Test commit retrieval with until parameter."""
        with patch("commitlog.run_git") as mock_git:
            mock_git.return_value = "abc123\tfeat: add feature\tTest User\t2026-01-01"
            commits = commitlog.get_commits(since="v0.1.0", until="v0.2.0")
            mock_git.assert_called_once()
            call_args = mock_git.call_args[0][0]
            self.assertIn("v0.1.0..v0.2.0", call_args)

    def test_get_commits_with_path(self):
        """Test commit retrieval with path filter."""
        with patch("commitlog.run_git") as mock_git:
            mock_git.return_value = "abc123\tfeat: add feature\tTest User\t2026-01-01"
            commits = commitlog.get_commits(path="src/")
            mock_git.assert_called_once()
            call_args = mock_git.call_args[0][0]
            self.assertIn("--", call_args)
            self.assertIn("src/", call_args)

    def test_get_commits_empty(self):
        """Test empty commit list."""
        with patch("commitlog.run_git") as mock_git:
            mock_git.return_value = ""
            commits = commitlog.get_commits()
            self.assertEqual(commits, [])

    def test_get_commits_multiple(self):
        """Test multiple commits."""
        with patch("commitlog.run_git") as mock_git:
            mock_git.return_value = (
                "abc123\tfeat: add feature\tTest User\t2026-01-01\n"
                "def456\tfix: bug fix\tTest User\t2026-01-02"
            )
            commits = commitlog.get_commits()
            self.assertEqual(len(commits), 2)

    def test_get_commits_with_body(self):
        """Test commit retrieval with body."""
        with patch("commitlog.run_git") as mock_git:
            mock_git.return_value = "abc123\tfeat: add feature\tTest User\t2026-01-01\tBody text"
            commits = commitlog.get_commits(include_body=True)
            self.assertEqual(len(commits), 1)
            self.assertEqual(commits[0]["body"], "Body text")

    def test_no_git_repo(self):
        """Should exit when not in a git repo."""
        original_dir = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                os.chdir(tmpdir)
                with self.assertRaises(SystemExit):
                    commitlog.get_commits()
            finally:
                os.chdir(original_dir)


class TestParseConventionalCommit(unittest.TestCase):
    """Test conventional commit parsing."""

    def test_feat(self):
        result = commitlog.parse_conventional_commit("feat: add new feature")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "feat")
        self.assertIsNone(result["scope"])
        self.assertEqual(result["description"], "add new feature")
        self.assertFalse(result["is_breaking"])

    def test_feat_with_scope(self):
        result = commitlog.parse_conventional_commit("feat(api): add endpoint")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "feat")
        self.assertEqual(result["scope"], "api")
        self.assertEqual(result["description"], "add endpoint")

    def test_fix(self):
        result = commitlog.parse_conventional_commit("fix: resolve bug")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "fix")
        self.assertEqual(result["description"], "resolve bug")

    def test_docs(self):
        result = commitlog.parse_conventional_commit("docs: update README")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "docs")

    def test_chore(self):
        result = commitlog.parse_conventional_commit("chore: cleanup")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "chore")

    def test_refactor(self):
        result = commitlog.parse_conventional_commit("refactor: simplify logic")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "refactor")

    def test_breaking_change(self):
        result = commitlog.parse_conventional_commit("feat!: remove deprecated API")
        self.assertIsNotNone(result)
        self.assertTrue(result["is_breaking"])

    def test_breaking_change_with_scope(self):
        result = commitlog.parse_conventional_commit("feat(api)!: remove endpoint")
        self.assertIsNotNone(result)
        self.assertTrue(result["is_breaking"])
        self.assertEqual(result["scope"], "api")

    def test_breaking_change_in_body(self):
        """BREAKING CHANGE: in body should be detected."""
        body = "Some description\n\nBREAKING CHANGE: this breaks the API"
        result = commitlog.parse_conventional_commit("feat: add feature", body)
        self.assertIsNotNone(result)
        self.assertTrue(result["is_breaking"])

    def test_no_false_positive_breaking(self):
        """'breaking news' in description should NOT be flagged as breaking."""
        result = commitlog.parse_conventional_commit("fix: handle breaking news API")
        self.assertIsNotNone(result)
        self.assertFalse(result["is_breaking"])

    def test_non_conventional(self):
        result = commitlog.parse_conventional_commit("random commit message")
        self.assertIsNone(result)

    def test_empty(self):
        result = commitlog.parse_conventional_commit("")
        self.assertIsNone(result)


class TestClassifyCommits(unittest.TestCase):
    """Test commit classification."""

    def test_classify_features(self):
        commits = [
            {"subject": "feat: add feature A", "hash": "abc123", "short_hash": "abc123", "author": "test", "date": "2026-01-01"},
            {"subject": "feat: add feature B", "hash": "def456", "short_hash": "def456", "author": "test", "date": "2026-01-02"},
        ]
        sections = commitlog.classify_commits(commits)
        self.assertIn("features", sections)
        self.assertEqual(len(sections["features"]), 2)

    def test_classify_fixes(self):
        commits = [
            {"subject": "fix: resolve bug", "hash": "abc123", "short_hash": "abc123", "author": "test", "date": "2026-01-01"},
        ]
        sections = commitlog.classify_commits(commits)
        self.assertIn("fixes", sections)
        self.assertEqual(len(sections["fixes"]), 1)

    def test_classify_docs(self):
        commits = [
            {"subject": "docs: update README", "hash": "abc123", "short_hash": "abc123", "author": "test", "date": "2026-01-01"},
        ]
        sections = commitlog.classify_commits(commits)
        self.assertIn("docs", sections)

    def test_classify_other(self):
        commits = [
            {"subject": "chore: cleanup", "hash": "abc123", "short_hash": "abc123", "author": "test", "date": "2026-01-01"},
            {"subject": "refactor: simplify", "hash": "def456", "short_hash": "def456", "author": "test", "date": "2026-01-02"},
        ]
        sections = commitlog.classify_commits(commits)
        self.assertIn("other", sections)
        self.assertEqual(len(sections["other"]), 2)

    def test_classify_mixed(self):
        commits = [
            {"subject": "feat: new feature", "hash": "a", "short_hash": "a", "author": "t", "date": "2026-01-01"},
            {"subject": "fix: bug fix", "hash": "b", "short_hash": "b", "author": "t", "date": "2026-01-02"},
            {"subject": "docs: update", "hash": "c", "short_hash": "c", "author": "t", "date": "2026-01-03"},
            {"subject": "chore: cleanup", "hash": "d", "short_hash": "d", "author": "t", "date": "2026-01-04"},
        ]
        sections = commitlog.classify_commits(commits)
        self.assertEqual(len(sections["features"]), 1)
        self.assertEqual(len(sections["fixes"]), 1)
        self.assertEqual(len(sections["docs"]), 1)
        self.assertEqual(len(sections["other"]), 1)

    def test_classify_non_conventional(self):
        commits = [
            {"subject": "random message", "hash": "a", "short_hash": "a", "author": "t", "date": "2026-01-01"},
        ]
        sections = commitlog.classify_commits(commits)
        self.assertIn("other", sections)

    def test_empty(self):
        sections = commitlog.classify_commits([])
        self.assertEqual(sections, {})


class TestGenerateMarkdown(unittest.TestCase):
    """Test Markdown generation."""

    def test_basic_markdown(self):
        sections = {
            "features": [
                {"description": "add feature", "scope": "api", "short_hash": "abc1234", "hash": "abc1234567890", "is_breaking": False}
            ]
        }
        output = commitlog.generate_markdown(sections, version="v1.0.0", date="2026-01-01")
        self.assertIn("## v1.0.0 (2026-01-01)", output)
        self.assertIn("### Features", output)
        self.assertIn("**api**", output)
        self.assertIn("add feature", output)
        self.assertIn("abc1234", output)

    def test_multiple_sections(self):
        sections = {
            "features": [
                {"description": "new feature", "scope": None, "short_hash": "a", "hash": "a", "is_breaking": False}
            ],
            "fixes": [
                {"description": "fix bug", "scope": None, "short_hash": "b", "hash": "b", "is_breaking": False}
            ],
        }
        output = commitlog.generate_markdown(sections, version="v1.0.0", date="2026-01-01")
        self.assertIn("Features", output)
        self.assertIn("Bug Fixes", output)

    def test_breaking_change(self):
        sections = {
            "features": [
                {"description": "remove API", "scope": None, "short_hash": "a", "hash": "a", "is_breaking": True}
            ]
        }
        output = commitlog.generate_markdown(sections, version="v1.0.0", date="2026-01-01")
        self.assertIn("[BREAKING]", output)

    def test_empty_sections(self):
        output = commitlog.generate_markdown({}, version="v1.0.0", date="2026-01-01")
        self.assertIn("## v1.0.0 (2026-01-01)", output)

    def test_with_repo_url(self):
        sections = {
            "features": [
                {"description": "add feature", "scope": None, "short_hash": "abc1234", "hash": "abc1234567890", "is_breaking": False}
            ]
        }
        output = commitlog.generate_markdown(
            sections, version="v1.0.0", date="2026-01-01",
            repo_url="https://github.com/user/repo"
        )
        self.assertIn("https://github.com/user/repo/commit/abc1234567890", output)


class TestGenerateText(unittest.TestCase):
    """Test plain text generation."""

    def test_basic_text(self):
        sections = {
            "features": [
                {"description": "add feature", "scope": "api", "short_hash": "abc1234", "hash": "abc1234567890", "is_breaking": False}
            ]
        }
        output = commitlog.generate_text(sections, version="v1.0.0", date="2026-01-01")
        self.assertIn("v1.0.0 (2026-01-01)", output)
        self.assertIn("Features:", output)
        self.assertIn("[api] add feature", output)

    def test_no_scope(self):
        sections = {
            "features": [
                {"description": "add feature", "scope": None, "short_hash": "a", "hash": "a", "is_breaking": False}
            ]
        }
        output = commitlog.generate_text(sections, version="v1.0.0", date="2026-01-01")
        self.assertIn("add feature", output)


class TestGenerateJson(unittest.TestCase):
    """Test JSON generation."""

    def test_basic_json(self):
        sections = {
            "features": [
                {"description": "add feature", "scope": "api", "short_hash": "abc1234", "hash": "abc1234567890", "author": "test", "date": "2026-01-01", "is_breaking": False}
            ]
        }
        output = commitlog.generate_json(sections, version="v1.0.0", date="2026-01-01")
        parsed = json.loads(output)
        self.assertEqual(parsed["version"], "v1.0.0")
        self.assertIn("features", parsed["sections"])
        self.assertEqual(parsed["sections"]["features"][0]["scope"], "api")

    def test_empty_json(self):
        output = commitlog.generate_json({}, version="v1.0.0", date="2026-01-01")
        parsed = json.loads(output)
        self.assertEqual(parsed["sections"], {})


class TestLoadConfig(unittest.TestCase):
    """Test config loading."""

    def test_load_existing_config(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump({"default_since": "v1.0"}, f)
            config = commitlog.load_config(path)
            self.assertEqual(config["default_since"], "v1.0")
        finally:
            os.unlink(path)

    def test_load_missing_config(self):
        config = commitlog.load_config("/nonexistent/path.json")
        self.assertEqual(config, {})

    def test_load_invalid_json(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                f.write("{invalid json")
            config = commitlog.load_config(path)
            self.assertEqual(config, {})
        finally:
            os.unlink(path)


class TestGetLastTag(unittest.TestCase):
    """Test get_last_tag function."""

    def test_get_last_tag_success(self):
        with patch("commitlog.run_git") as mock_git:
            mock_git.return_value = "v1.0.0"
            result = commitlog.get_last_tag()
            self.assertEqual(result, "v1.0.0")

    def test_get_last_tag_no_tags(self):
        """Should return None when no tags exist."""
        with patch("commitlog.run_git") as mock_git:
            mock_git.side_effect = SystemExit()
            result = commitlog.get_last_tag()
            self.assertIsNone(result)


class TestInitCommand(unittest.TestCase):
    """Test init command."""

    def test_init_creates_config(self):
        """Test that init creates a config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_dir = os.getcwd()
            try:
                os.chdir(tmpdir)
                args = argparse.Namespace()
                commitlog.init_command(args)
                self.assertTrue(os.path.exists("commitlog.json"))
                with open("commitlog.json") as f:
                    config = json.load(f)
                self.assertIn("grouping", config)
                self.assertIn("default_since", config)
            finally:
                os.chdir(original_dir)

    def test_init_overwrite_prompt(self):
        """Test that init prompts before overwriting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_dir = os.getcwd()
            try:
                os.chdir(tmpdir)
                # Create existing config
                with open("commitlog.json", "w") as f:
                    json.dump({"test": True}, f)

                args = argparse.Namespace()
                with patch("builtins.input", return_value="n"):
                    commitlog.init_command(args)

                # Config should not be overwritten
                with open("commitlog.json") as f:
                    config = json.load(f)
                self.assertIn("test", config)
            finally:
                os.chdir(original_dir)


class TestGenerateCommand(unittest.TestCase):
    """Test generate command with mocks."""

    def test_generate_command_markdown(self):
        """Test generate command with markdown output."""
        with patch("commitlog.get_commits") as mock_commits:
            mock_commits.return_value = [
                {"subject": "feat: add feature", "hash": "a" * 40, "short_hash": "a" * 7, "author": "test", "date": "2026-01-01"},
            ]
            args = argparse.Namespace(
                since=None,
                until=None,
                path=None,
                format="markdown",
                output=None,
                scope_filter=None,
                no_group=False,
                include_body=False,
            )
            with patch("commitlog.load_config", return_value={}):
                with patch("builtins.print") as mock_print:
                    commitlog.generate_command(args)
                    mock_print.assert_called()

    def test_generate_command_json(self):
        """Test generate command with JSON output."""
        with patch("commitlog.get_commits") as mock_commits:
            mock_commits.return_value = [
                {"subject": "feat: add feature", "hash": "a" * 40, "short_hash": "a" * 7, "author": "test", "date": "2026-01-01"},
            ]
            args = argparse.Namespace(
                since=None,
                until=None,
                path=None,
                format="json",
                output=None,
                scope_filter=None,
                no_group=False,
                include_body=False,
            )
            with patch("commitlog.load_config", return_value={}):
                with patch("builtins.print") as mock_print:
                    commitlog.generate_command(args)
                    mock_print.assert_called()

    def test_generate_command_text(self):
        """Test generate command with text output."""
        with patch("commitlog.get_commits") as mock_commits:
            mock_commits.return_value = [
                {"subject": "feat: add feature", "hash": "a" * 40, "short_hash": "a" * 7, "author": "test", "date": "2026-01-01"},
            ]
            args = argparse.Namespace(
                since=None,
                until=None,
                path=None,
                format="text",
                output=None,
                scope_filter=None,
                no_group=False,
                include_body=False,
            )
            with patch("commitlog.load_config", return_value={}):
                with patch("builtins.print") as mock_print:
                    commitlog.generate_command(args)
                    mock_print.assert_called()

    def test_generate_command_with_output_file(self):
        """Test generate command writes to file."""
        with patch("commitlog.get_commits") as mock_commits:
            mock_commits.return_value = [
                {"subject": "feat: add feature", "hash": "a" * 40, "short_hash": "a" * 7, "author": "test", "date": "2026-01-01"},
            ]
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
                output_path = f.name

            try:
                args = argparse.Namespace(
                    since=None,
                    until=None,
                    path=None,
                    format="markdown",
                    output=output_path,
                    scope_filter=None,
                    no_group=False,
                    include_body=False,
                )
                with patch("commitlog.load_config", return_value={}):
                    commitlog.generate_command(args)

                with open(output_path) as f:
                    content = f.read()
                self.assertIn("Features", content)
            finally:
                os.unlink(output_path)

    def test_generate_command_with_scope_filter(self):
        """Test generate command with scope filter."""
        with patch("commitlog.get_commits") as mock_commits:
            mock_commits.return_value = [
                {"subject": "feat(api): add feature", "hash": "a" * 40, "short_hash": "a" * 7, "author": "test", "date": "2026-01-01"},
                {"subject": "feat(ui): add button", "hash": "b" * 40, "short_hash": "b" * 7, "author": "test", "date": "2026-01-02"},
            ]
            args = argparse.Namespace(
                since=None,
                until=None,
                path=None,
                format="markdown",
                output=None,
                scope_filter="api",
                no_group=False,
                include_body=False,
            )
            with patch("commitlog.load_config", return_value={}):
                with patch("builtins.print") as mock_print:
                    commitlog.generate_command(args)
                    output = mock_print.call_args[0][0]
                    self.assertIn("api", output)
                    self.assertNotIn("ui", output)

    def test_generate_command_no_group(self):
        """Test generate command without grouping."""
        with patch("commitlog.get_commits") as mock_commits:
            mock_commits.return_value = [
                {"subject": "feat: add feature", "hash": "a" * 40, "short_hash": "a" * 7, "author": "test", "date": "2026-01-01"},
                {"subject": "fix: bug fix", "hash": "b" * 40, "short_hash": "b" * 7, "author": "test", "date": "2026-01-02"},
            ]
            args = argparse.Namespace(
                since=None,
                until=None,
                path=None,
                format="markdown",
                output=None,
                scope_filter=None,
                no_group=True,
                include_body=False,
            )
            with patch("commitlog.load_config", return_value={}):
                with patch("builtins.print") as mock_print:
                    commitlog.generate_command(args)
                    output = mock_print.call_args[0][0]
                    # Should have "Changes" section instead of grouped
                    self.assertIn("Changes", output)

    def test_generate_command_last_tag(self):
        """Test generate command with last_tag as since."""
        with patch("commitlog.get_commits") as mock_commits:
            with patch("commitlog.get_last_tag", return_value="v1.0.0"):
                mock_commits.return_value = [
                    {"subject": "feat: add feature", "hash": "a" * 40, "short_hash": "a" * 7, "author": "test", "date": "2026-01-01"},
                ]
                args = argparse.Namespace(
                    since="last_tag",
                    until=None,
                    path=None,
                    format="markdown",
                    output=None,
                    scope_filter=None,
                    no_group=False,
                    include_body=False,
                )
                with patch("commitlog.load_config", return_value={}):
                    commitlog.generate_command(args)
                    # Verify get_commits was called with the tag
                    mock_commits.assert_called_once()
                    call_kwargs = mock_commits.call_args[1]
                    self.assertEqual(call_kwargs["since"], "v1.0.0")


class TestEndToEnd(unittest.TestCase):
    """End-to-end tests."""

    def test_full_workflow(self):
        """Test full commit processing workflow."""
        commits = [
            {"subject": "feat: add user API", "hash": "a" * 40, "short_hash": "a" * 7, "author": "test", "date": "2026-01-01"},
            {"subject": "fix: resolve login bug", "hash": "b" * 40, "short_hash": "b" * 7, "author": "test", "date": "2026-01-02"},
            {"subject": "docs: update README", "hash": "c" * 40, "short_hash": "c" * 7, "author": "test", "date": "2026-01-03"},
            {"subject": "chore: cleanup", "hash": "d" * 40, "short_hash": "d" * 7, "author": "test", "date": "2026-01-04"},
        ]

        sections = commitlog.classify_commits(commits)
        self.assertEqual(len(sections["features"]), 1)
        self.assertEqual(len(sections["fixes"]), 1)
        self.assertEqual(len(sections["docs"]), 1)
        self.assertEqual(len(sections["other"]), 1)

        markdown = commitlog.generate_markdown(sections, version="v1.0.0", date="2026-01-01")
        self.assertIn("Features", markdown)
        self.assertIn("Bug Fixes", markdown)
        self.assertIn("Documentation", markdown)
        self.assertIn("Other", markdown)

        json_output = commitlog.generate_json(sections, version="v1.0.0", date="2026-01-01")
        parsed = json.loads(json_output)
        self.assertEqual(len(parsed["sections"]["features"]), 1)

    def test_breaking_change_body_workflow(self):
        """Test that BREAKING CHANGE: in body is detected."""
        commits = [
            {"subject": "feat: add feature", "hash": "a" * 40, "short_hash": "a" * 7, "author": "test", "date": "2026-01-01", "body": "Details\n\nBREAKING CHANGE: old API removed"},
        ]
        sections = commitlog.classify_commits(commits)
        self.assertTrue(sections["features"][0]["is_breaking"])


if __name__ == "__main__":
    unittest.main()
