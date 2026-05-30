import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import tempfile
import hashlib
from core.scanner import scan_directory
from core.detector import find_duplicates


class TestFindDuplicates:

    def test_unique_content_no_duplicates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, "a.txt")
            file2 = os.path.join(tmpdir, "b.txt")

            with open(file1, "w") as f:
                f.write("unique content A")
            with open(file2, "w") as f:
                f.write("unique content B")

            file_infos = scan_directory(tmpdir)
            results = find_duplicates(file_infos, "test_share")

            assert isinstance(results, list)
            assert len(results) == 0

    def test_two_identical_files_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, "copy1.txt")
            file2 = os.path.join(tmpdir, "copy2.txt")

            content = "identical content here!"
            with open(file1, "w") as f:
                f.write(content)
            with open(file2, "w") as f:
                f.write(content)

            file_infos = scan_directory(tmpdir)
            results = find_duplicates(file_infos, "test_share")

            assert len(results) == 1
            group_id, shared_folder, md5_hex, file_list = results[0]
            assert group_id == 1
            assert shared_folder == "test_share"
            assert isinstance(md5_hex, str)
            assert len(md5_hex) == 32
            assert len(file_list) == 2

    def test_same_size_different_content_not_duplicates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, "same_size_1.txt")
            file2 = os.path.join(tmpdir, "same_size_2.txt")

            with open(file1, "w") as f:
                f.write("A" * 100)
            with open(file2, "w") as f:
                f.write("B" * 100)

            file_infos = scan_directory(tmpdir)
            results = find_duplicates(file_infos, "test_share")

            assert len(results) == 0

    def test_md5_algorithm(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, "md5_1.txt")
            file2 = os.path.join(tmpdir, "md5_2.txt")

            with open(file1, "w") as f:
                f.write("same content")
            with open(file2, "w") as f:
                f.write("same content")

            file_infos = scan_directory(tmpdir)
            results = find_duplicates(file_infos, "test_share", algorithm="md5")

            assert len(results) == 1
            expected_md5 = hashlib.md5(b"same content").hexdigest()
            assert results[0][2] == expected_md5

    def test_sha256_algorithm(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, "sha_1.txt")
            file2 = os.path.join(tmpdir, "sha_2.txt")

            with open(file1, "w") as f:
                f.write("same content")
            with open(file2, "w") as f:
                f.write("same content")

            file_infos = scan_directory(tmpdir)
            results = find_duplicates(file_infos, "test_share", algorithm="sha256")

            assert len(results) == 1
            expected_sha = hashlib.sha256(b"same content").hexdigest()
            assert results[0][2] == expected_sha
            assert len(results[0][2]) == 64

    def test_return_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, "dup_a.txt")
            file2 = os.path.join(tmpdir, "dup_b.txt")

            with open(file1, "w") as f:
                f.write("duplicate content")
            with open(file2, "w") as f:
                f.write("duplicate content")

            file_infos = scan_directory(tmpdir)
            results = find_duplicates(file_infos, "my_share")

            assert len(results) == 1
            group_id, shared_folder, md5_hex, file_list = results[0]

            assert isinstance(group_id, int)
            assert shared_folder == "my_share"
            assert isinstance(md5_hex, str)
            assert isinstance(file_list, list)
            assert len(file_list) == 2

            for file_info in file_list:
                assert isinstance(file_info, tuple)
                assert len(file_info) == 4
                full_path, filename, size, mtime_str = file_info
                assert isinstance(full_path, str)
                assert isinstance(filename, str)
                assert isinstance(size, int)
                assert isinstance(mtime_str, str)

    def test_progress_callback_stages(self):
        stages_seen = set()

        def progress_callback(stage, current, total):
            stages_seen.add(stage)
            assert isinstance(stage, str)
            assert isinstance(current, int)
            assert isinstance(total, int)

        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, "p1.txt")
            file2 = os.path.join(tmpdir, "p2.txt")
            with open(file1, "w") as f:
                f.write("dup")
            with open(file2, "w") as f:
                f.write("dup")

            file_infos = scan_directory(tmpdir)
            find_duplicates(file_infos, "test_share", progress_callback=progress_callback)

        assert "size_grouping" in stages_seen
        assert "hashing" in stages_seen
        assert "done" in stages_seen

    def test_empty_file_list(self):
        results = find_duplicates([], "empty_share")
        assert isinstance(results, list)
        assert len(results) == 0

    def test_single_file_no_duplicates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, "only.txt")
            with open(file1, "w") as f:
                f.write("only one file")

            file_infos = scan_directory(tmpdir)
            results = find_duplicates(file_infos, "test_share")

            assert len(results) == 0

    def test_three_identical_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                filepath = os.path.join(tmpdir, f"dup{i}.txt")
                with open(filepath, "w") as f:
                    f.write("triple duplicate!")

            file_infos = scan_directory(tmpdir)
            results = find_duplicates(file_infos, "test_share")

            assert len(results) == 1
            assert len(results[0][3]) == 3

    def test_multiple_duplicate_groups(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, "groupA_1.txt")
            file2 = os.path.join(tmpdir, "groupA_2.txt")
            file3 = os.path.join(tmpdir, "groupB_1.txt")
            file4 = os.path.join(tmpdir, "groupB_2.txt")

            with open(file1, "w") as f:
                f.write("group A content")
            with open(file2, "w") as f:
                f.write("group A content")
            with open(file3, "w") as f:
                f.write("group B content different!")
            with open(file4, "w") as f:
                f.write("group B content different!")

            file_infos = scan_directory(tmpdir)
            results = find_duplicates(file_infos, "test_share")

            assert len(results) == 2
            for result in results:
                assert len(result[3]) == 2

    def test_invalid_algorithm_raises_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, "f1.txt")
            file2 = os.path.join(tmpdir, "f2.txt")
            with open(file1, "w") as f:
                f.write("content")
            with open(file2, "w") as f:
                f.write("content")

            file_infos = scan_directory(tmpdir)
            with pytest.raises(ValueError, match="不支持的哈希算法"):
                find_duplicates(file_infos, "test_share", algorithm="sha1")

    def test_algorithm_case_insensitive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, "f1.txt")
            file2 = os.path.join(tmpdir, "f2.txt")
            with open(file1, "w") as f:
                f.write("content")
            with open(file2, "w") as f:
                f.write("content")

            file_infos = scan_directory(tmpdir)
            results = find_duplicates(file_infos, "test_share", algorithm="MD5")
            assert len(results) == 1

    def test_files_with_same_content_different_names(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, "report_final.docx")
            file2 = os.path.join(tmpdir, "report_final_copy.docx")

            with open(file1, "w") as f:
                f.write("binary_like_content")
            with open(file2, "w") as f:
                f.write("binary_like_content")

            file_infos = scan_directory(tmpdir)
            results = find_duplicates(file_infos, "test_share")

            assert len(results) == 1

    def test_group_ids_are_sequential(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, "a1.txt")
            file2 = os.path.join(tmpdir, "a2.txt")
            file3 = os.path.join(tmpdir, "b1.txt")
            file4 = os.path.join(tmpdir, "b2.txt")

            with open(file1, "w") as f:
                f.write("AAAA")
            with open(file2, "w") as f:
                f.write("AAAA")
            with open(file3, "w") as f:
                f.write("BBBBBB")
            with open(file4, "w") as f:
                f.write("BBBBBB")

            file_infos = scan_directory(tmpdir)
            results = find_duplicates(file_infos, "test_share")

            assert len(results) == 2
            group_ids = [r[0] for r in results]
            assert sorted(group_ids) == [1, 2]
