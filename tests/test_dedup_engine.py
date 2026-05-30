import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import tempfile
import json
from pathlib import Path
from core.pattern_manager import PatternManager
from core.dedup_engine import DedupEngine


def _make_pm_with_patterns(patterns=None):
    tmpdir = tempfile.mkdtemp()
    filepath = Path(tmpdir) / "patterns.json"
    if patterns is None:
        patterns = [
            {"pattern": "/node_modules/", "name": "Node.js 依赖", "enabled": True},
            {"pattern": "/\\.git/", "name": "Git 版本控制", "enabled": True},
        ]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(patterns, f, ensure_ascii=False, indent=2)
    pm = PatternManager(filepath)
    pm.load()
    return pm


class TestScorePath:

    def test_score_path_returns_number(self):
        pm = _make_pm_with_patterns()
        engine = DedupEngine(pm)

        score = engine.score_path("/home/user/Documents/report.txt")
        assert isinstance(score, float)

    def test_higher_score_for_better_path(self):
        pm = _make_pm_with_patterns()
        engine = DedupEngine(pm)

        score_good = engine.score_path("/home/user/Materials/素材/photo.jpg")
        score_bad = engine.score_path("/tmp/新建文件夹/WindowsTimemachine/dup.jpg")

        assert score_good > score_bad

    def test_deeper_path_gets_penalty(self):
        pm = _make_pm_with_patterns()
        engine = DedupEngine(pm)

        score_shallow = engine.score_path("/a/file.txt")
        score_deep = engine.score_path("/a/b/c/d/e/f/g/file.txt")

        assert score_shallow > score_deep

    def test_timestamp_suffix_penalty(self):
        pm = _make_pm_with_patterns()
        engine = DedupEngine(pm)

        score_normal = engine.score_path("/home/user/file.txt")
        score_timestamp = engine.score_path("/home/user/file_20230101120000.txt")

        assert score_normal > score_timestamp

    def test_copy_suffix_penalty(self):
        pm = _make_pm_with_patterns()
        engine = DedupEngine(pm)

        score_original = engine.score_path("/home/user/file.txt")
        score_copy = engine.score_path("/home/user/file (1).txt")

        assert score_original > score_copy

    def test_base_prefixes_stripped(self):
        pm = _make_pm_with_patterns()
        engine = DedupEngine(pm)

        path = "/mnt/share/subdir/file.txt"
        score_with_prefix = engine.score_path(path, base_prefixes=["/mnt/share/"])

        score_same = engine.score_path("subdir/file.txt")

        assert score_with_prefix == score_same

    def test_bad_keywords_penalty(self):
        pm = _make_pm_with_patterns()
        engine = DedupEngine(pm)

        score_normal = engine.score_path("/home/user/docs/report.txt")
        score_bad = engine.score_path("/home/user/新建文件夹/Dataset_2/report.txt")

        assert score_normal > score_bad

    def test_good_keywords_bonus(self):
        pm = _make_pm_with_patterns()
        engine = DedupEngine(pm)

        score_normal = engine.score_path("/home/user/docs/report.txt")
        score_good = engine.score_path("/home/user/Important/report.txt")

        assert score_good > score_normal


class TestAnalyzeGroup:
    def test_keep_best_mode(self):
        pm = _make_pm_with_patterns()
        engine = DedupEngine(pm)

        files = [
            {"path": "/home/user/Desktop/新建文件夹/copy.txt", "size": 100, "mtime": "2024-01-01T00:00:00"},
            {"path": "/home/user/Documents/Important/report.txt", "size": 100, "mtime": "2024-01-01T00:00:00"},
            {"path": "/home/user/Downloads/draft.txt", "size": 100, "mtime": "2024-01-01T00:00:00"},
        ]

        result = engine.analyze_group(1, files, mode="keep_best")

        assert result["group_id"] == 1
        assert result["keep"] is not None
        assert "Important" in result["keep"]["path"]
        assert len(result["remove"]) == 2
        assert len(result["protected"]) == 0
        assert result["office_temp_cleanup"] is False

    def test_keep_largest_mode(self):
        pm = _make_pm_with_patterns()
        engine = DedupEngine(pm)

        files = [
            {"path": "/a/small.txt", "size": 10, "mtime": "2024-01-01T00:00:00"},
            {"path": "/b/medium.txt", "size": 100, "mtime": "2024-01-01T00:00:00"},
            {"path": "/c/large.txt", "size": 1000, "mtime": "2024-01-01T00:00:00"},
        ]

        result = engine.analyze_group(1, files, mode="keep_largest")

        assert result["keep"]["path"] == "/c/large.txt"
        assert result["keep"]["size"] == 1000
        assert len(result["remove"]) == 2

    def test_keep_largest_with_string_size(self):
        pm = _make_pm_with_patterns()
        engine = DedupEngine(pm)

        files = [
            {"path": "/a/small.txt", "size": "10", "mtime": "2024-01-01T00:00:00"},
            {"path": "/b/large.txt", "size": "1000", "mtime": "2024-01-01T00:00:00"},
        ]

        result = engine.analyze_group(1, files, mode="keep_largest")

        assert result["keep"] is not None
        assert result["keep"]["size"] == "1000"

    def test_keep_newest_mode(self):
        pm = _make_pm_with_patterns()
        engine = DedupEngine(pm)

        files = [
            {"path": "/a/old.txt", "size": 100, "mtime": "2023-01-01T00:00:00"},
            {"path": "/b/mid.txt", "size": 100, "mtime": "2024-06-01T00:00:00"},
            {"path": "/c/new.txt", "size": 100, "mtime": "2025-01-01T00:00:00"},
        ]

        result = engine.analyze_group(1, files, mode="keep_newest")

        assert result["keep"]["path"] == "/c/new.txt"
        assert result["keep"]["mtime"] == "2025-01-01T00:00:00"
        assert len(result["remove"]) == 2

    def test_analyze_group_with_single_file(self):
        pm = _make_pm_with_patterns()
        engine = DedupEngine(pm)

        files = [{"path": "/a/only.txt", "size": 100, "mtime": "2024-01-01T00:00:00"}]

        result = engine.analyze_group(1, files, mode="keep_best")

        assert result["keep"] is not None
        assert result["keep"]["path"] == "/a/only.txt"
        assert len(result["remove"]) == 0
        assert len(result["protected"]) == 0

    def test_analyze_group_with_empty_list(self):
        pm = _make_pm_with_patterns()
        engine = DedupEngine(pm)

        result = engine.analyze_group(1, [], mode="keep_best")

        assert result["keep"] is None
        assert len(result["remove"]) == 0
        assert len(result["protected"]) == 0

    def test_office_temp_files_all_deleted(self):
        pm = _make_pm_with_patterns()
        engine = DedupEngine(pm)

        files = [
            {"path": "/tmp/~$report.docx", "size": 100, "mtime": "2024-01-01T00:00:00"},
            {"path": "/tmp/~$notes.docx", "size": 100, "mtime": "2024-01-01T00:00:00"},
        ]

        result = engine.analyze_group(1, files, mode="keep_best")

        assert result["office_temp_cleanup"] is True
        assert result["keep"] is None
        assert len(result["remove"]) == 2
        assert len(result["protected"]) == 0

    def test_mixed_office_temp_and_normal(self):
        pm = _make_pm_with_patterns()
        engine = DedupEngine(pm)

        files = [
            {"path": "/tmp/~$report.docx", "size": 100, "mtime": "2024-01-01T00:00:00"},
            {"path": "/tmp/report.docx", "size": 100, "mtime": "2024-01-01T00:00:00"},
        ]

        result = engine.analyze_group(1, files, mode="keep_best")

        assert result["office_temp_cleanup"] is False

    def test_protected_files_identified(self):
        pm = _make_pm_with_patterns()
        engine = DedupEngine(pm)

        files = [
            {"path": "/project/node_modules/pkg/index.js", "size": 100, "mtime": "2024-01-01T00:00:00"},
            {"path": "/project/lib/pkg/index.js", "size": 100, "mtime": "2024-01-01T00:00:00"},
        ]

        result = engine.analyze_group(1, files, mode="keep_best")

        assert len(result["protected"]) == 1
        assert "node_modules" in result["protected"][0]["path"]
        assert result["protected"][0]["protect_category"] == "Node.js 依赖"
        assert result["keep"] is not None
        assert "lib" in result["keep"]["path"]
        assert len(result["remove"]) == 0

    def test_all_protected_no_removals(self):
        pm = _make_pm_with_patterns()
        engine = DedupEngine(pm)

        files = [
            {"path": "/project/node_modules/a/index.js", "size": 100, "mtime": "2024-01-01T00:00:00"},
            {"path": "/project/node_modules/b/index.js", "size": 100, "mtime": "2024-01-01T00:00:00"},
        ]

        result = engine.analyze_group(1, files, mode="keep_best")

        assert len(result["protected"]) == 2
        assert result["keep"] is None
        assert len(result["remove"]) == 0


class TestAnalyzeAll:

    def test_analyze_all_returns_results_for_all_groups(self):
        pm = _make_pm_with_patterns()
        engine = DedupEngine(pm)

        dup_groups = {
            1: [
                {"path": "/home/user/docs/a.txt", "size": 100, "mtime": "2024-01-01T00:00:00"},
                {"path": "/home/user/docs/b.txt", "size": 100, "mtime": "2024-01-01T00:00:00"},
            ],
            2: [
                {"path": "/home/user/docs/c.txt", "size": 200, "mtime": "2024-01-01T00:00:00"},
                {"path": "/home/user/docs/d.txt", "size": 200, "mtime": "2024-01-01T00:00:00"},
            ],
        }

        results = engine.analyze_all(dup_groups, mode="keep_best")

        assert len(results) == 2
        assert {r["group_id"] for r in results} == {1, 2}

    def test_analyze_all_with_string_group_ids(self):
        pm = _make_pm_with_patterns()
        engine = DedupEngine(pm)

        dup_groups = {
            "1": [
                {"path": "/a/f1.txt", "size": 100, "mtime": "2024-01-01T00:00:00"},
                {"path": "/a/f2.txt", "size": 100, "mtime": "2024-01-01T00:00:00"},
            ],
            "2": [
                {"path": "/b/f3.txt", "size": 200, "mtime": "2024-01-01T00:00:00"},
                {"path": "/b/f4.txt", "size": 200, "mtime": "2024-01-01T00:00:00"},
            ],
        }

        results = engine.analyze_all(dup_groups, mode="keep_best")
        assert len(results) == 2


class TestGetSummary:

    def test_get_summary_returns_correct_statistics(self):
        pm = _make_pm_with_patterns()
        engine = DedupEngine(pm)

        analysis_results = [
            {
                "group_id": 1,
                "keep": {"path": "/a/keep.txt", "size": 100},
                "remove": [
                    {"path": "/a/remove1.txt", "size": 100},
                    {"path": "/a/remove2.txt", "size": 100},
                ],
                "protected": [],
                "office_temp_cleanup": False,
            },
            {
                "group_id": 2,
                "keep": None,
                "remove": [{"path": "/tmp/~$temp.docx", "size": 50}],
                "protected": [],
                "office_temp_cleanup": True,
            },
            {
                "group_id": 3,
                "keep": None,
                "remove": [],
                "protected": [
                    {"path": "/p/node_modules/a.js", "size": 200, "protect_category": "Node.js 依赖"},
                    {"path": "/p/node_modules/b.js", "size": 200, "protect_category": "Node.js 依赖"},
                ],
                "office_temp_cleanup": False,
            },
        ]

        summary = engine.get_summary(analysis_results)

        assert summary["total_groups"] == 3
        assert summary["total_remove_files"] == 3
        assert summary["total_protected_files"] == 2
        assert summary["total_keep_files"] == 1
        assert summary["office_temp_groups"] == 1
        assert summary["office_temp_files"] == 1
        assert summary["all_protected_groups"] == 1
        assert "Node.js 依赖" in summary["category_stats"]
        assert summary["category_stats"]["Node.js 依赖"] == 2

    def test_get_summary_empty_results(self):
        pm = _make_pm_with_patterns()
        engine = DedupEngine(pm)

        summary = engine.get_summary([])

        assert summary["total_groups"] == 0
        assert summary["total_remove_files"] == 0
        assert summary["total_protected_files"] == 0
        assert summary["total_keep_files"] == 0
        assert summary["office_temp_groups"] == 0
        assert summary["office_temp_files"] == 0
        assert summary["all_protected_groups"] == 0
        assert isinstance(summary["category_stats"], dict)
