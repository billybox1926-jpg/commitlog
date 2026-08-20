#!/usr/bin/env python3
"""Tests for commitlog v0.1.0."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

import commitlog


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
            {
                "subject": "feat: add feature A",
                "hash": "abc123",
                "short_hash": "abc123",
                "author": "test",
                "date": "2026-01-01",
            },
            {
                "subject": "feat: add feature B",
                "hash": "def456",
                "short_hash": "def456",
                "author": "test",
                "date": "2026-01-02",
            },
        ]
        sections = commitlog.classify_commits(commits)
        self.assertIn("features", sections)
        self.assertEqual(len(sections["features"]), 2)

    def test_classify_fixes(self):
        commits = [
            {
                "subject": "fix: resolve bug",
                "hash": "abc123",
                "short_hash": "abc123",
                "author": "test",
                "date": "2026-01-01",
            },
        ]
        sections = commitlog.classify_commits(commits)
        self.assertIn("fixes", sections)
        self.assertEqual(len(sections["fixes"]), 1)

    def test_classify_docs(self):
        commits = [
            {
                "subject": "docs: update README",
                "hash": "abc123",
                "short_hash": "abc123",
                "author": "test",
                "date": "2026-01-01",
            },
        ]
        sections = commitlog.classify_commits(commits)
        self.assertIn("docs", sections)

    def test_classify_other(self):
        commits = [
            {
                "subject": "chore: cleanup",
                "hash": "abc123",
                "short_hash": "abc123",
                "author": "test",
                "date": "2026-01-01",
            },
            {
                "subject": "refactor: simplify",
                "hash": "def456",
                "short_hash": "def456",
                "author": "test",
                "date": "2026-01-02",
            },
        ]
        sections = commitlog.classify_commits(commits)
        self.assertIn("other", sections)
        self.assertEqual(len(sections["other"]), 2)

    def test_classify_mixed(self):
        commits = [
            {
                "subject": "feat: new feature",
                "hash": "a",
                "short_hash": "a",
                "author": "t",
                "date": "2026-01-01",
            },
            {
                "subject": "fix: bug fix",
                "hash": "b",
                "short_hash": "b",
                "author": "t",
                "date": "2026-01-02",
            },
            {
                "subject": "docs: update",
                "hash": "c",
                "short_hash": "c",
                "author": "t",
                "date": "2026-01-03",
            },
            {
                "subject": "chore: cleanup",
                "hash": "d",
                "short_hash": "d",
                "author": "t",
                "date": "2026-01-04",
            },
        ]
        sections = commitlog.classify_commits(commits)
        self.assertEqual(len(sections["features"]), 1)
        self.assertEqual(len(sections["fixes"]), 1)
        self.assertEqual(len(sections["docs"]), 1)
        self.assertEqual(len(sections["other"]), 1)

    def test_classify_non_conventional(self):
        commits = [
            {
                "subject": "random message",
                "hash": "a",
                "short_hash": "a",
                "author": "t",
                "date": "2026-01-01",
            },
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
                {
                    "description": "add feature",
                    "scope": "api",
                    "short_hash": "abc1234",
                    "hash": "abc1234567890",
                    "is_breaking": False,
                }
            ]
        }
        output = commitlog.generate_markdown(
            sections, version="v1.0.0", date="2026-01-01"
        )
        self.assertIn("## v1.0.0 (2026-01-01)", output)
        self.assertIn("### Features", output)
        self.assertIn("**api**", output)
        self.assertIn("add feature", output)
        self.assertIn("abc1234", output)

    def test_multiple_sections(self):
        sections = {
            "features": [
                {
                    "description": "new feature",
                    "scope": None,
                    "short_hash": "a",
                    "hash": "a",
                    "is_breaking": False,
                }
            ],
            "fixes": [
                {
                    "description": "fix bug",
                    "scope": None,
                    "short_hash": "b",
                    "hash": "b",
                    "is_breaking": False,
                }
            ],
        }
        output = commitlog.generate_markdown(
            sections, version="v1.0.0", date="2026-01-01"
        )
        self.assertIn("Features", output)
        self.assertIn("Bug Fixes", output)

    def test_breaking_change(self):
        sections = {
            "features": [
                {
                    "description": "remove API",
                    "scope": None,
                    "short_hash": "a",
                    "hash": "a",
                    "is_breaking": True,
                }
            ]
        }
        output = commitlog.generate_markdown(
            sections, version="v1.0.0", date="2026-01-01"
        )
        self.assertIn("[BREAKING]", output)

    def test_empty_sections(self):
        output = commitlog.generate_markdown({}, version="v1.0.0", date="2026-01-01")
        self.assertIn("## v1.0.0 (2026-01-01)", output)


class TestGenerateText(unittest.TestCase):
    """Test plain text generation."""

    def test_basic_text(self):
        sections = {
            "features": [
                {
                    "description": "add feature",
                    "scope": "api",
                    "short_hash": "abc1234",
                    "hash": "abc1234567890",
                    "is_breaking": False,
                }
            ]
        }
        output = commitlog.generate_text(sections, version="v1.0.0", date="2026-01-01")
        self.assertIn("v1.0.0 (2026-01-01)", output)
        self.assertIn("Features:", output)
        self.assertIn("[api] add feature", output)

    def test_no_scope(self):
        sections = {
            "features": [
                {
                    "description": "add feature",
                    "scope": None,
                    "short_hash": "a",
                    "hash": "a",
                    "is_breaking": False,
                }
            ]
        }
        output = commitlog.generate_text(sections, version="v1.0.0", date="2026-01-01")
        self.assertIn("add feature", output)


class TestGenerateJson(unittest.TestCase):
    """Test JSON generation."""

    def test_basic_json(self):
        sections = {
            "features": [
                {
                    "description": "add feature",
                    "scope": "api",
                    "short_hash": "abc1234",
                    "hash": "abc1234567890",
                    "author": "test",
                    "date": "2026-01-01",
                    "is_breaking": False,
                }
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


class TestGetCommits(unittest.TestCase):
    """Test git commit retrieval."""

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


class TestEndToEnd(unittest.TestCase):
    """End-to-end tests."""

    def test_full_workflow(self):
        """Test full commit processing workflow."""
        commits = [
            {
                "subject": "feat: add user API",
                "hash": "a" * 40,
                "short_hash": "a" * 7,
                "author": "test",
                "date": "2026-01-01",
            },
            {
                "subject": "fix: resolve login bug",
                "hash": "b" * 40,
                "short_hash": "b" * 7,
                "author": "test",
                "date": "2026-01-02",
            },
            {
                "subject": "docs: update README",
                "hash": "c" * 40,
                "short_hash": "c" * 7,
                "author": "test",
                "date": "2026-01-03",
            },
            {
                "subject": "chore: cleanup",
                "hash": "d" * 40,
                "short_hash": "d" * 7,
                "author": "test",
                "date": "2026-01-04",
            },
        ]

        sections = commitlog.classify_commits(commits)
        self.assertEqual(len(sections["features"]), 1)
        self.assertEqual(len(sections["fixes"]), 1)
        self.assertEqual(len(sections["docs"]), 1)
        self.assertEqual(len(sections["other"]), 1)

        markdown = commitlog.generate_markdown(
            sections, version="v1.0.0", date="2026-01-01"
        )
        self.assertIn("Features", markdown)
        self.assertIn("Bug Fixes", markdown)
        self.assertIn("Documentation", markdown)
        self.assertIn("Other", markdown)

        json_output = commitlog.generate_json(
            sections, version="v1.0.0", date="2026-01-01"
        )
        parsed = json.loads(json_output)
        self.assertEqual(len(parsed["sections"]["features"]), 1)


if __name__ == "__main__":
    unittest.main()
