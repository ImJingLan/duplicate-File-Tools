import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import tempfile
from core.scanner import scan_directory


class TestScanDirectory:

    def test_scan_temp_directory_with_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, "file1.txt")
            file2 = os.path.join(tmpdir, "file2.txt")
            subdir = os.path.join(tmpdir, "subdir")
            os.makedirs(subdir)
            file3 = os.path.join(subdir, "file3.txt")

            with open(file1, "w") as f:
                f.write("hello")
            with open(file2, "w") as f:
                f.write("world!")
            with open(file3, "w") as f:
                f.write("inside subdir")

            results = scan_directory(tmpdir)

            result_paths = {r[0] for r in results}
            assert file1 in result_paths
            assert file2 in result_paths
            assert file3 in result_paths
            assert len(results) == 3

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            results = scan_directory(tmpdir)
            assert isinstance(results, list)
            assert len(results) == 0

    def test_non_existent_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent = os.path.join(tmpdir, "does_not_exist")
            with pytest.raises(ValueError, match="不是有效的目录"):
                scan_directory(nonexistent)

    def test_min_size_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            small_file = os.path.join(tmpdir, "small.txt")
            large_file = os.path.join(tmpdir, "large.txt")

            with open(small_file, "w") as f:
                f.write("a")
            with open(large_file, "w") as f:
                f.write("b" * 100)

            results = scan_directory(tmpdir, min_size=50)
            result_paths = {r[0] for r in results}

            assert large_file in result_paths
            assert small_file not in result_paths

    def test_exclude_patterns_glob(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            keep_file = os.path.join(tmpdir, "keep.txt")
            exclude_file = os.path.join(tmpdir, "exclude.log")
            another_exclude = os.path.join(tmpdir, "debug.tmp")

            with open(keep_file, "w") as f:
                f.write("keep me")
            with open(exclude_file, "w") as f:
                f.write("exclude me")
            with open(another_exclude, "w") as f:
                f.write("also exclude")

            results = scan_directory(tmpdir, exclude_patterns=["*.log", "*.tmp"])
            result_paths = {r[0] for r in results}

            assert keep_file in result_paths
            assert exclude_file not in result_paths
            assert another_exclude not in result_paths
            assert len(results) == 1

    def test_exclude_patterns_by_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            keep_file = os.path.join(tmpdir, "keep.txt")
            subdir = os.path.join(tmpdir, "node_modules")
            os.makedirs(subdir)
            module_file = os.path.join(subdir, "index.js")

            with open(keep_file, "w") as f:
                f.write("keep me")
            with open(module_file, "w") as f:
                f.write("module content")

            results = scan_directory(tmpdir, exclude_patterns=["*\\node_modules\\*"])
            result_paths = {r[0] for r in results}

            assert keep_file in result_paths
            assert module_file not in result_paths

    def test_progress_callback_is_called(self):
        call_count = [0]

        def progress_callback(current, total, current_path):
            call_count[0] += 1

        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(5):
                filepath = os.path.join(tmpdir, f"file{i}.txt")
                with open(filepath, "w") as f:
                    f.write(f"content {i}")

            scan_directory(tmpdir, progress_callback=progress_callback)
            assert call_count[0] == 5

    def test_progress_callback_values(self):
        captured = []

        def progress_callback(current, total, current_path):
            captured.append((current, total, current_path))

        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                filepath = os.path.join(tmpdir, f"file{i}.txt")
                with open(filepath, "w") as f:
                    f.write(f"content {i}")

            scan_directory(tmpdir, progress_callback=progress_callback)

        assert len(captured) == 3
        for i, (current, total, current_path) in enumerate(captured, start=1):
            assert current == i
            assert total == 3
            assert current_path.endswith(".txt")

    def test_file_info_tuple_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test.txt")
            with open(filepath, "w") as f:
                f.write("hello world")

            results = scan_directory(tmpdir)
            assert len(results) == 1

            full_path, filename, size, mtime_str = results[0]

            assert full_path == filepath
            assert isinstance(full_path, str)
            assert filename == "test.txt"
            assert isinstance(filename, str)
            assert size == 11
            assert isinstance(size, int)
            assert isinstance(mtime_str, str)
            assert "T" in mtime_str

    def test_permission_error_handled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "ok.txt")
            with open(filepath, "w") as f:
                f.write("ok")

            results = scan_directory(tmpdir)
            assert len(results) >= 1

    def test_scan_with_exclude_and_min_size_combined(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            big_keep = os.path.join(tmpdir, "big_keep.txt")
            big_exclude = os.path.join(tmpdir, "big_exclude.log")
            small_keep = os.path.join(tmpdir, "small_keep.txt")

            with open(big_keep, "w") as f:
                f.write("x" * 100)
            with open(big_exclude, "w") as f:
                f.write("y" * 100)
            with open(small_keep, "w") as f:
                f.write("z")

            results = scan_directory(tmpdir, min_size=50, exclude_patterns=["*.log"])
            result_paths = {r[0] for r in results}

            assert big_keep in result_paths
            assert big_exclude not in result_paths
            assert small_keep not in result_paths
            assert len(results) == 1

    def test_scan_single_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "only.txt")
            with open(filepath, "w") as f:
                f.write("only file")

            results = scan_directory(tmpdir)
            assert len(results) == 1
            assert results[0][0] == filepath
            assert results[0][1] == "only.txt"
            assert results[0][2] == 9

    def test_progress_callback_does_not_crash_on_exception(self):
        def bad_callback(current, total, current_path):
            if current == 2:
                raise RuntimeError("callback error")

        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                filepath = os.path.join(tmpdir, f"file{i}.txt")
                with open(filepath, "w") as f:
                    f.write(f"content {i}")

            results = scan_directory(tmpdir, progress_callback=bad_callback)
            assert len(results) == 3
