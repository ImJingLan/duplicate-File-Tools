import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import tempfile
import json
import hashlib
from pathlib import Path
from core.scanner import scan_directory
from core.detector import find_duplicates
from core.pattern_manager import PatternManager
from core.dedup_engine import DedupEngine
from core.script_generator import (
    generate_batch_script,
    generate_shell_script,
    generate_analysis_report,
    save_script,
)


class TestFullFlow:

    def test_scan_detect_analyze_generate_script(self):
        with tempfile.TemporaryDirectory() as scan_dir:
            file1 = os.path.join(scan_dir, "Documents", "Important", "report.txt")
            file2 = os.path.join(scan_dir, "Downloads", "report_copy.txt")
            file3 = os.path.join(scan_dir, "Desktop", "backup_report.txt")
            os.makedirs(os.path.dirname(file1))
            os.makedirs(os.path.dirname(file2))
            os.makedirs(os.path.dirname(file3))

            content = "Quarterly Financial Report 2024\nConfidential"
            for fp in [file1, file2, file3]:
                with open(fp, "w") as f:
                    f.write(content)

            file_infos = scan_directory(scan_dir)
            assert len(file_infos) >= 3

            dup_results = find_duplicates(file_infos, "test_scan", algorithm="md5")
            assert len(dup_results) == 1

            group_id, shared_folder, md5_hex, file_list = dup_results[0]
            assert len(file_list) == 3

            assert len(md5_hex) == 32
            with open(file1, "rb") as f:
                expected_md5 = hashlib.md5(f.read()).hexdigest()
            assert md5_hex == expected_md5

            dup_groups = {
                group_id: [
                    {"path": fp, "size": os.path.getsize(fp), "mtime": "2024-01-01T00:00:00"}
                    for fp, fn, sz, mt in file_list
                ]
            }

            pm_file = Path(tempfile.mkdtemp()) / "patterns.json"
            with open(pm_file, "w", encoding="utf-8") as f:
                json.dump([], f)
            pm = PatternManager(pm_file)
            pm.load()

            engine = DedupEngine(pm)
            analysis_results = engine.analyze_all(dup_groups, mode="keep_best")

            assert len(analysis_results) == 1
            result = analysis_results[0]
            assert result["keep"] is not None
            assert len(result["remove"]) == 2
            assert len(result["protected"]) == 0

            with tempfile.TemporaryDirectory() as output_dir:
                staging = os.path.join(output_dir, "staging")
                report = os.path.join(output_dir, "report.txt")
                script_path = os.path.join(output_dir, "run.bat")

                bat_script = generate_batch_script(analysis_results, staging, report)
                assert len(bat_script) > 0
                assert "@echo off" in bat_script

                save_script(bat_script, script_path)
                assert os.path.exists(script_path)

    def test_scanner_detector_work_together(self):
        with tempfile.TemporaryDirectory() as scan_dir:
            sub1 = os.path.join(scan_dir, "dir_a")
            sub2 = os.path.join(scan_dir, "dir_b")
            os.makedirs(sub1)
            os.makedirs(sub2)

            unique_content = "unique file in dir_a"
            dup_content = "DUPLICATE_CONTENT_12345"

            with open(os.path.join(sub1, "unique.txt"), "w") as f:
                f.write(unique_content)
            with open(os.path.join(sub1, "dup1.txt"), "w") as f:
                f.write(dup_content)
            with open(os.path.join(sub2, "dup2.txt"), "w") as f:
                f.write(dup_content)
            with open(os.path.join(sub2, "other.txt"), "w") as f:
                f.write("another file entirely")

            file_infos = scan_directory(scan_dir)
            assert len(file_infos) == 4

            dup_results = find_duplicates(file_infos, "integration_test")
            assert len(dup_results) == 1
            assert len(dup_results[0][3]) == 2

            paths = {f[0] for f in dup_results[0][3]}
            assert os.path.join(sub1, "dup1.txt") in paths
            assert os.path.join(sub2, "dup2.txt") in paths

    def test_dedup_engine_processes_detector_output(self):
        with tempfile.TemporaryDirectory() as scan_dir:
            file1 = os.path.join(scan_dir, "Important_Docs", "master.txt")
            file2 = os.path.join(scan_dir, "Old_2205", "copy.txt")
            file3 = os.path.join(scan_dir, "Desktop", "backup.txt")
            os.makedirs(os.path.dirname(file1))
            os.makedirs(os.path.dirname(file2))
            os.makedirs(os.path.dirname(file3))

            content = "Project Alpha Design Document v2.0"
            for fp in [file1, file2, file3]:
                with open(fp, "w") as f:
                    f.write(content)

            file_infos = scan_directory(scan_dir)
            dup_results = find_duplicates(file_infos, "test_scan", algorithm="md5")

            dup_groups = {}
            for group_id, shared_folder, md5_hex, file_list in dup_results:
                dup_groups[group_id] = [
                    {"path": fp, "size": sz, "mtime": mt}
                    for fp, fn, sz, mt in file_list
                ]

            pm_file = Path(tempfile.mkdtemp()) / "patterns.json"
            with open(pm_file, "w", encoding="utf-8") as f:
                json.dump([], f)
            pm = PatternManager(pm_file)
            pm.load()

            engine = DedupEngine(pm)
            analysis_results = engine.analyze_all(dup_groups, mode="keep_best")

            assert len(analysis_results) == 1
            result = analysis_results[0]
            assert result["keep"] is not None
            assert "Important_Docs" in result["keep"]["path"]
            assert len(result["remove"]) == 2

            remove_paths = {f["path"] for f in result["remove"]}
            assert file2 in remove_paths
            assert file3 in remove_paths

    def test_with_protected_patterns_integration(self):
        with tempfile.TemporaryDirectory() as scan_dir:
            node_modules = os.path.join(scan_dir, "node_modules", "lib")
            src_dir = os.path.join(scan_dir, "src")
            os.makedirs(node_modules)
            os.makedirs(src_dir)

            content = "same binary content"
            node_file = os.path.join(node_modules, "module.js")
            src_file = os.path.join(src_dir, "module.js")
            with open(node_file, "w") as f:
                f.write(content)
            with open(src_file, "w") as f:
                f.write(content)

            file_infos = scan_directory(scan_dir)
            dup_results = find_duplicates(file_infos, "test_scan", algorithm="md5")

            dup_groups = {}
            for group_id, shared_folder, md5_hex, file_list in dup_results:
                dup_groups[group_id] = [
                    {"path": fp, "size": sz, "mtime": mt}
                    for fp, fn, sz, mt in file_list
                ]

            pm_file = Path(tempfile.mkdtemp()) / "patterns.json"
            patterns_data = [
                {"pattern": r"node_modules", "name": "Node.js 依赖", "enabled": True},
            ]
            with open(pm_file, "w", encoding="utf-8") as f:
                json.dump(patterns_data, f, ensure_ascii=False, indent=2)
            pm = PatternManager(pm_file)
            pm.load()

            engine = DedupEngine(pm)
            analysis_results = engine.analyze_all(dup_groups, mode="keep_best")

            assert len(analysis_results) == 1
            result = analysis_results[0]

            assert len(result["protected"]) == 1
            assert "node_modules" in result["protected"][0]["path"]
            assert result["protected"][0]["protect_category"] == "Node.js 依赖"

            assert result["keep"] is not None
            assert src_file in result["keep"]["path"]
            assert len(result["remove"]) == 0

    def test_generate_all_script_types(self):
        with tempfile.TemporaryDirectory() as scan_dir:
            file1 = os.path.join(scan_dir, "a.txt")
            file2 = os.path.join(scan_dir, "b.txt")
            with open(file1, "w") as f:
                f.write("duplicate")
            with open(file2, "w") as f:
                f.write("duplicate")

            file_infos = scan_directory(scan_dir)
            dup_results = find_duplicates(file_infos, "test_scan")

            dup_groups = {}
            for group_id, shared_folder, md5_hex, file_list in dup_results:
                dup_groups[group_id] = [
                    {"path": fp, "size": sz, "mtime": mt}
                    for fp, fn, sz, mt in file_list
                ]

            pm_file = Path(tempfile.mkdtemp()) / "patterns.json"
            with open(pm_file, "w", encoding="utf-8") as f:
                json.dump([], f)
            pm = PatternManager(pm_file)
            pm.load()

            engine = DedupEngine(pm)
            analysis_results = engine.analyze_all(dup_groups, mode="keep_best")

            with tempfile.TemporaryDirectory() as output_dir:
                staging = os.path.join(output_dir, "staging")
                report = os.path.join(output_dir, "report.txt")

                bat = generate_batch_script(analysis_results, staging, report)
                sh = generate_shell_script(analysis_results, "/tmp/staging", "/tmp/report.txt")
                rep = generate_analysis_report(analysis_results, dup_groups)

                assert len(bat) > 0
                assert len(sh) > 0
                assert len(rep) > 0

                save_script(bat, os.path.join(output_dir, "run.bat"))
                save_script(sh, os.path.join(output_dir, "run.sh"))

                assert os.path.exists(os.path.join(output_dir, "run.bat"))
                assert os.path.exists(os.path.join(output_dir, "run.sh"))

    def test_empty_scan_results_full_flow(self):
        with tempfile.TemporaryDirectory() as scan_dir:
            file_infos = scan_directory(scan_dir)
            assert len(file_infos) == 0

            dup_results = find_duplicates(file_infos, "empty_scan")
            assert len(dup_results) == 0

            dup_groups = {}
            pm_file = Path(tempfile.mkdtemp()) / "patterns.json"
            with open(pm_file, "w", encoding="utf-8") as f:
                json.dump([], f)
            pm = PatternManager(pm_file)
            pm.load()

            engine = DedupEngine(pm)
            analysis_results = engine.analyze_all(dup_groups)
            assert len(analysis_results) == 0

            summary = engine.get_summary(analysis_results)
            assert summary["total_groups"] == 0
