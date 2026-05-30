import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import tempfile
import json
from pathlib import Path
from core.pattern_manager import PatternManager


@pytest.fixture
def empty_patterns_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "patterns.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump([], f)
        yield filepath


@pytest.fixture
def populated_patterns_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "patterns.json"
        data = [
            {"pattern": "/node_modules/", "name": "Node.js 依赖", "enabled": True},
            {"pattern": "/\\.git/", "name": "Git 版本控制", "enabled": True},
            {"pattern": "\\.log$", "name": "日志文件", "enabled": False},
        ]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        yield filepath


class TestPatternManagerLoad:
    def test_load_patterns_from_json(self, populated_patterns_file):
        pm = PatternManager(populated_patterns_file)
        patterns = pm.load()

        assert len(patterns) == 3
        assert patterns[0]["pattern"] == "/node_modules/"
        assert patterns[0]["name"] == "Node.js 依赖"
        assert patterns[0]["enabled"] is True
        assert patterns[2]["pattern"] == r"\.log$"
        assert patterns[2]["enabled"] is False

    def test_load_empty_file(self, empty_patterns_file):
        pm = PatternManager(empty_patterns_file)
        patterns = pm.load()

        assert isinstance(patterns, list)
        assert len(patterns) == 0

    def test_load_nonexistent_file(self):
        pm = PatternManager(Path("/nonexistent/path/patterns.json"))
        patterns = pm.load()

        assert isinstance(patterns, list)
        assert len(patterns) == 0

    def test_load_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "bad_patterns.json"
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("this is not json")

            pm = PatternManager(filepath)
            patterns = pm.load()

            assert isinstance(patterns, list)
            assert len(patterns) == 0

    def test_load_not_a_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "obj_patterns.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump({"key": "value"}, f)

            pm = PatternManager(filepath)
            patterns = pm.load()

            assert isinstance(patterns, list)
            assert len(patterns) == 0


class TestPatternManagerAdd:
    def test_add_pattern_with_valid_regex(self, empty_patterns_file):
        pm = PatternManager(empty_patterns_file)
        pm.load()

        success, error_msg = pm.add(r"/vendor/", "PHP 依赖", enabled=True)

        assert success is True
        assert error_msg == ""
        all_patterns = pm.get_all()
        assert len(all_patterns) == 1
        assert all_patterns[0]["pattern"] == "/vendor/"
        assert all_patterns[0]["name"] == "PHP 依赖"
        assert all_patterns[0]["enabled"] is True

    def test_add_pattern_with_invalid_regex(self, empty_patterns_file):
        pm = PatternManager(empty_patterns_file)
        pm.load()

        success, error_msg = pm.add(r"[invalid(", "Bad Regex", enabled=True)

        assert success is False
        assert error_msg != ""
        all_patterns = pm.get_all()
        assert len(all_patterns) == 0

    def test_add_disabled_pattern(self, empty_patterns_file):
        pm = PatternManager(empty_patterns_file)
        pm.load()

        success, _ = pm.add(r"/steam/", "Steam 平台", enabled=False)

        assert success is True
        all_patterns = pm.get_all()
        assert all_patterns[0]["enabled"] is False
        enabled = pm.get_enabled()
        assert len(enabled) == 0


class TestPatternManagerUpdate:
    def test_update_pattern_string(self, populated_patterns_file):
        pm = PatternManager(populated_patterns_file)
        pm.load()

        success, error_msg = pm.update(0, pattern_str="/new_pattern/")

        assert success is True
        assert error_msg == ""
        assert pm.get_all()[0]["pattern"] == "/new_pattern/"

    def test_update_name(self, populated_patterns_file):
        pm = PatternManager(populated_patterns_file)
        pm.load()

        success, _ = pm.update(1, name="Updated Name")

        assert success is True
        assert pm.get_all()[1]["name"] == "Updated Name"

    def test_update_enabled_status(self, populated_patterns_file):
        pm = PatternManager(populated_patterns_file)
        pm.load()

        success, _ = pm.update(2, enabled=True)

        assert success is True
        assert pm.get_all()[2]["enabled"] is True

    def test_update_with_invalid_regex(self, populated_patterns_file):
        pm = PatternManager(populated_patterns_file)
        pm.load()

        success, error_msg = pm.update(0, pattern_str="[invalid[[")

        assert success is False
        assert error_msg != ""

    def test_update_out_of_range_index(self, populated_patterns_file):
        pm = PatternManager(populated_patterns_file)
        pm.load()

        success, error_msg = pm.update(99, name="Nonexistent")

        assert success is False
        assert "超出范围" in error_msg

    def test_update_none_fields_preserved(self, populated_patterns_file):
        pm = PatternManager(populated_patterns_file)
        pm.load()

        original = pm.get_all()[0].copy()
        success, _ = pm.update(0, name=None, enabled=None)

        assert success is True
        updated = pm.get_all()[0]
        assert updated["pattern"] == original["pattern"]
        assert updated["name"] == original["name"]
        assert updated["enabled"] == original["enabled"]


class TestPatternManagerDelete:
    def test_delete_pattern(self, populated_patterns_file):
        pm = PatternManager(populated_patterns_file)
        pm.load()
        original_count = len(pm.get_all())

        success, error_msg = pm.delete(0)

        assert success is True
        assert error_msg == ""
        assert len(pm.get_all()) == original_count - 1

    def test_delete_out_of_range(self, populated_patterns_file):
        pm = PatternManager(populated_patterns_file)
        pm.load()

        success, error_msg = pm.delete(99)

        assert success is False
        assert "超出范围" in error_msg

    def test_delete_negative_index(self, populated_patterns_file):
        pm = PatternManager(populated_patterns_file)
        pm.load()

        success, error_msg = pm.delete(-1)

        assert success is False
        assert "超出范围" in error_msg


class TestPatternManagerMove:
    def test_move_pattern(self, populated_patterns_file):
        pm = PatternManager(populated_patterns_file)
        pm.load()
        original_first = pm.get_all()[0]["name"]

        success, error_msg = pm.move(0, 2)

        assert success is True
        assert error_msg == ""
        assert pm.get_all()[2]["name"] == original_first

    def test_move_same_index(self, populated_patterns_file):
        pm = PatternManager(populated_patterns_file)
        pm.load()
        all_before = [p["name"] for p in pm.get_all()]

        success, error_msg = pm.move(1, 1)

        assert success is True
        all_after = [p["name"] for p in pm.get_all()]
        assert all_before == all_after

    def test_move_out_of_range_from(self, populated_patterns_file):
        pm = PatternManager(populated_patterns_file)
        pm.load()

        success, error_msg = pm.move(99, 0)

        assert success is False
        assert "源索引" in error_msg

    def test_move_out_of_range_to(self, populated_patterns_file):
        pm = PatternManager(populated_patterns_file)
        pm.load()

        success, error_msg = pm.move(0, 99)

        assert success is False
        assert "目标索引" in error_msg


class TestPatternManagerProtection:
    def test_is_protected_matching_path(self, populated_patterns_file):
        pm = PatternManager(populated_patterns_file)
        pm.load()

        is_protected, category = pm.is_protected("/home/user/project/node_modules/express/index.js")

        assert is_protected is True
        assert category == "Node.js 依赖"

    def test_is_protected_non_matching_path(self, populated_patterns_file):
        pm = PatternManager(populated_patterns_file)
        pm.load()

        is_protected, category = pm.is_protected("/home/user/documents/report.txt")

        assert is_protected is False
        assert category == ""

    def test_is_protected_disabled_pattern_not_used(self, populated_patterns_file):
        pm = PatternManager(populated_patterns_file)
        pm.load()

        is_protected, category = pm.is_protected("/var/log/app.log")

        assert is_protected is False
        assert category == ""

    def test_is_protected_empty_list(self, empty_patterns_file):
        pm = PatternManager(empty_patterns_file)
        pm.load()

        is_protected, category = pm.is_protected("/any/path/file.txt")

        assert is_protected is False
        assert category == ""


class TestPatternManagerTestMatch:
    def test_test_match_returns_correct_matches(self, populated_patterns_file):
        pm = PatternManager(populated_patterns_file)
        pm.load()

        matches = pm.test_match("/project/src/node_modules/pkg/lib.js")

        assert len(matches) == 1
        assert matches[0]["pattern"] == "/node_modules/"
        assert matches[0]["name"] == "Node.js 依赖"

    def test_test_match_no_matches(self, populated_patterns_file):
        pm = PatternManager(populated_patterns_file)
        pm.load()

        matches = pm.test_match("/home/user/data.csv")

        assert isinstance(matches, list)
        assert len(matches) == 0

    def test_test_match_multiple_matches(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "patterns.json"
            data = [
                {"pattern": "/game/", "name": "游戏文件", "enabled": True},
                {"pattern": "Half-Life", "name": "Half-Life 引擎", "enabled": True},
            ]
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f)

            pm = PatternManager(filepath)
            pm.load()

            matches = pm.test_match("/home/user/Half-Life/game/cstrike/")

            assert len(matches) == 2
            match_names = {m["name"] for m in matches}
            assert "游戏文件" in match_names
            assert "Half-Life 引擎" in match_names


class TestPatternManagerToggle:
    def test_toggle_enabled_disabled(self, populated_patterns_file):
        pm = PatternManager(populated_patterns_file)
        pm.load()

        success, _ = pm.update(1, enabled=False)
        assert success is True
        assert pm.get_all()[1]["enabled"] is False

        enabled = pm.get_enabled()
        enabled_names = [e[1] for e in enabled]
        assert "Git 版本控制" not in enabled_names

        success, _ = pm.update(1, enabled=True)
        assert success is True
        assert pm.get_all()[1]["enabled"] is True

        enabled = pm.get_enabled()
        enabled_names = [e[1] for e in enabled]
        assert "Git 版本控制" in enabled_names


class TestPatternManagerSave:
    def test_save_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "saved_patterns.json"
            pm = PatternManager(filepath)
            pm.add(r"/docker/", "Docker 文件")
            pm.save()

            assert filepath.exists()
            with open(filepath, "r", encoding="utf-8") as f:
                saved = json.load(f)
            assert len(saved) == 1
            assert saved[0]["pattern"] == "/docker/"
            assert saved[0]["name"] == "Docker 文件"

    def test_save_with_provided_patterns(self, empty_patterns_file):
        pm = PatternManager(empty_patterns_file)
        pm.load()

        new_patterns = [
            {"pattern": "/src/", "name": "源码", "enabled": True},
            {"pattern": "/lib/", "name": "库文件", "enabled": False},
        ]
        pm.save(new_patterns)

        all_patterns = pm.get_all()
        assert len(all_patterns) == 2
        assert all_patterns[0]["name"] == "源码"


class TestPatternManagerValidateRegex:
    def test_valid_regex(self):
        pm = PatternManager(Path("/nonexistent/patterns.json"))
        is_valid, error_msg = pm.validate_regex(r"test\d+")

        assert is_valid is True
        assert error_msg == ""

    def test_invalid_regex(self):
        pm = PatternManager(Path("/nonexistent/patterns.json"))
        is_valid, error_msg = pm.validate_regex(r"[unclosed")

        assert is_valid is False
        assert error_msg != ""


class TestPatternManagerGetAllEnabled:
    def test_get_all_contains_all_entries(self, populated_patterns_file):
        pm = PatternManager(populated_patterns_file)
        pm.load()

        all_p = pm.get_all()
        assert len(all_p) == 3

    def test_get_enabled_only_returns_enabled(self, populated_patterns_file):
        pm = PatternManager(populated_patterns_file)
        pm.load()

        enabled = pm.get_enabled()
        assert len(enabled) == 2

        for compiled, name, pattern_str in enabled:
            assert compiled is not None
            assert isinstance(name, str)
            assert isinstance(pattern_str, str)
