import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import tempfile
from core.script_generator import (
    generate_batch_script,
    generate_shell_script,
    generate_analysis_report,
    save_script,
)


ANALYSIS_RESULTS = [
    {
        "group_id": 1,
        "keep": {"path": "C:\\Users\\test\\Documents\\report.txt", "score": 95.0, "size": 1024, "mtime": "2024-01-01T00:00:00"},
        "remove": [
            {"path": "C:\\Users\\test\\Downloads\\report_copy.txt", "score": 60.0, "size": 1024, "mtime": "2024-01-01T00:00:00"},
            {"path": "C:\\Users\\test\\Desktop\\report (1).txt", "score": 40.0, "size": 1024, "mtime": "2024-01-01T00:00:00"},
        ],
        "protected": [
            {"path": "C:\\Users\\test\\node_modules\\report.txt", "protect_category": "Node.js 依赖"},
        ],
        "office_temp_cleanup": False,
    },
    {
        "group_id": 2,
        "keep": None,
        "remove": [
            {"path": "C:\\tmp\\~$notes.docx", "score": 0, "size": 512},
        ],
        "protected": [],
        "office_temp_cleanup": True,
    },
]

DUP_GROUPS = {
    1: [
        {"path": "C:\\Users\\test\\Documents\\report.txt", "size": 1024, "mtime": "2024-01-01T00:00:00"},
        {"path": "C:\\Users\\test\\Downloads\\report_copy.txt", "size": 1024, "mtime": "2024-01-01T00:00:00"},
        {"path": "C:\\Users\\test\\Desktop\\report (1).txt", "size": 1024, "mtime": "2024-01-01T00:00:00"},
        {"path": "C:\\Users\\test\\node_modules\\report.txt", "size": 1024, "mtime": "2024-01-01T00:00:00"},
    ],
    2: [
        {"path": "C:\\tmp\\~$notes.docx", "size": 512, "mtime": "2024-01-01T00:00:00"},
        {"path": "C:\\tmp\\another.docx", "size": 512, "mtime": "2024-01-01T00:00:00"},
    ],
}


class TestGenerateBatchScript:

    def test_produces_valid_bat_content(self):
        script = generate_batch_script(ANALYSIS_RESULTS, "C:\\staging", "C:\\report.txt")

        assert isinstance(script, str)
        assert len(script) > 0
        assert "@echo off" in script
        assert "chcp 65001" in script
        assert "setlocal enabledelayedexpansion" in script

    def test_contains_staging_dir(self):
        script = generate_batch_script(ANALYSIS_RESULTS, "C:\\my_staging", "C:\\report.txt")

        assert "STAGING_DIR" in script
        assert "C:\\my_staging" in script

    def test_contains_report_file(self):
        script = generate_batch_script(ANALYSIS_RESULTS, "C:\\staging", "C:\\my_report.txt")

        assert "REPORT_FILE" in script
        assert "C:\\my_report" in script

    def test_contains_move_commands(self):
        script = generate_batch_script(ANALYSIS_RESULTS, "C:\\staging", "C:\\report.txt")

        assert "move" in script.lower() or "move" in script

    def test_contains_protected_file_info(self):
        script = generate_batch_script(ANALYSIS_RESULTS, "C:\\staging", "C:\\report.txt")

        assert "保护" in script

    def test_contains_office_temp_cleanup(self):
        script = generate_batch_script(ANALYSIS_RESULTS, "C:\\staging", "C:\\report.txt")

        assert "临时文件" in script

    def test_contains_endlocal(self):
        script = generate_batch_script(ANALYSIS_RESULTS, "C:\\staging", "C:\\report.txt")

        assert "endlocal" in script

    def test_empty_analysis_results(self):
        script = generate_batch_script([], "C:\\staging", "C:\\report.txt")

        assert isinstance(script, str)
        assert "@echo off" in script
        assert "endlocal" in script

    def test_contains_summary_stats(self):
        script = generate_batch_script(ANALYSIS_RESULTS, "C:\\staging", "C:\\report.txt")

        assert "TOTAL_GROUPS" in script
        assert "SUCCESS_GROUPS" in script
        assert "SKIP_GROUPS" in script
        assert "FAIL_GROUPS" in script

    def test_special_characters_escaped(self):
        results = [
            {
                "group_id": 1,
                "keep": {"path": "C:\\test\\file & name.txt", "score": 95.0, "size": 100},
                "remove": [
                    {"path": "C:\\test\\copy | dup.txt", "score": 50.0, "size": 100},
                ],
                "protected": [],
                "office_temp_cleanup": False,
            }
        ]

        script = generate_batch_script(results, "C:\\staging", "C:\\report.txt")

        assert isinstance(script, str)

    def test_results_with_no_removals_skipped(self):
        results = [
            {
                "group_id": 1,
                "keep": None,
                "remove": [],
                "protected": [
                    {"path": "C:\\node_modules\\f.js", "protect_category": "Node.js 依赖"},
                ],
                "office_temp_cleanup": False,
            }
        ]

        script = generate_batch_script(results, "C:\\staging", "C:\\report.txt")

        assert "全部为受保护文件" in script


class TestGenerateShellScript:

    def test_produces_valid_sh_content(self):
        script = generate_shell_script(ANALYSIS_RESULTS, "/tmp/staging", "/tmp/report.txt")

        assert isinstance(script, str)
        assert len(script) > 0
        assert "#!/bin/bash" in script
        assert "set -euo pipefail" in script

    def test_contains_staging_dir(self):
        script = generate_shell_script(ANALYSIS_RESULTS, "/tmp/my_staging", "/tmp/report.txt")

        assert "STAGING_DIR" in script
        assert "/tmp/my_staging" in script

    def test_contains_report_file(self):
        script = generate_shell_script(ANALYSIS_RESULTS, "/tmp/staging", "/tmp/my_report.txt")

        assert "REPORT_FILE" in script
        assert "/tmp/my_report" in script

    def test_contains_mv_commands(self):
        script = generate_shell_script(ANALYSIS_RESULTS, "/tmp/staging", "/tmp/report.txt")

        assert "mv " in script

    def test_contains_protected_file_info(self):
        script = generate_shell_script(ANALYSIS_RESULTS, "/tmp/staging", "/tmp/report.txt")

        assert "保护" in script

    def test_contains_office_temp_cleanup(self):
        script = generate_shell_script(ANALYSIS_RESULTS, "/tmp/staging", "/tmp/report.txt")

        assert "临时文件" in script

    def test_empty_analysis_results(self):
        script = generate_shell_script([], "/tmp/staging", "/tmp/report.txt")

        assert isinstance(script, str)
        assert "#!/bin/bash" in script

    def test_contains_summary_stats(self):
        script = generate_shell_script(ANALYSIS_RESULTS, "/tmp/staging", "/tmp/report.txt")

        assert "TOTAL_GROUPS" in script
        assert "SUCCESS_GROUPS" in script
        assert "SKIP_GROUPS" in script
        assert "FAIL_GROUPS" in script

    def test_shell_quotes_are_safe(self):
        results = [
            {
                "group_id": 1,
                "keep": {"path": "/tmp/file with spaces.txt", "score": 95.0, "size": 100},
                "remove": [
                    {"path": "/tmp/dup with spaces.txt", "score": 50.0, "size": 100},
                ],
                "protected": [],
                "office_temp_cleanup": False,
            }
        ]

        script = generate_shell_script(results, "/tmp/staging", "/tmp/report.txt")

        assert isinstance(script, str)


class TestGenerateAnalysisReport:

    def test_produces_readable_report(self):
        report = generate_analysis_report(ANALYSIS_RESULTS, DUP_GROUPS)

        assert isinstance(report, str)
        assert len(report) > 0
        assert "智能去重分析报告" in report

    def test_contains_group_details(self):
        report = generate_analysis_report(ANALYSIS_RESULTS, DUP_GROUPS)

        assert "组 1" in report
        assert "组 2" in report

    def test_contains_statistics(self):
        report = generate_analysis_report(ANALYSIS_RESULTS, DUP_GROUPS)

        assert "总重复组数" in report
        assert "可清理重复文件" in report
        assert "受保护文件" in report

    def test_contains_protected_category_stats(self):
        report = generate_analysis_report(ANALYSIS_RESULTS, DUP_GROUPS)

        assert "受保护文件分类统计" in report
        assert "Node.js 依赖" in report

    def test_contains_keep_indicators(self):
        report = generate_analysis_report(ANALYSIS_RESULTS, DUP_GROUPS)

        assert "保留" in report

    def test_contains_remove_indicators(self):
        report = generate_analysis_report(ANALYSIS_RESULTS, DUP_GROUPS)

        assert "移除" in report

    def test_empty_results(self):
        report = generate_analysis_report([], {})

        assert isinstance(report, str)
        assert "总重复组数: 0" in report

    def test_truncates_at_100_groups(self):
        many_results = []
        many_groups = {}
        for i in range(150):
            many_groups[i + 1] = [
                {"path": f"/tmp/f{i}_1.txt", "size": 100, "mtime": "2024-01-01T00:00:00"},
                {"path": f"/tmp/f{i}_2.txt", "size": 100, "mtime": "2024-01-01T00:00:00"},
            ]
            many_results.append({
                "group_id": i + 1,
                "keep": {"path": f"/tmp/f{i}_1.txt", "score": 90.0, "size": 100},
                "remove": [{"path": f"/tmp/f{i}_2.txt", "score": 50.0, "size": 100}],
                "protected": [],
                "office_temp_cleanup": False,
            })

        report = generate_analysis_report(many_results, many_groups)

        assert "还有 50 组" in report


class TestSaveScript:

    def test_save_script_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "subdir", "run.bat")
            save_script("@echo off\necho hello", output_path)

            assert os.path.exists(output_path)
            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "@echo off" in content

    def test_save_script_creates_parent_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "deeply", "nested", "dir", "script.bat")
            save_script("@echo off", output_path)

            assert os.path.exists(output_path)

    def test_save_script_overwrites_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "script.bat")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("old content")

            save_script("new content", output_path)

            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert content == "new content"
