"""
重复文件检测模块

采用多阶段策略高效检测重复文件：
1. 按文件大小分组（只处理大小相同的多个文件）
2. 对候选文件计算哈希值（MD5 或 SHA-256）
3. 哈希值相同的文件视为重复文件

支持线程池并行计算哈希值以提升性能。
"""

import hashlib
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from config.settings import CHUNK_SIZE

logger = logging.getLogger("core.detector")


def _compute_hash(full_path, algorithm):
    """
    计算单个文件的哈希值。

    以分块读取的方式计算文件的哈希摘要，避免大文件一次性加载到内存。

    Args:
        full_path: 文件完整路径
        algorithm: 哈希算法名称，支持 "md5" 或 "sha256"

    Returns:
        (full_path, hex_digest) 元组，文件路径和十六进制哈希值；若读取失败则返回 (full_path, None)
    """
    try:
        if algorithm == "sha256":
            hasher = hashlib.sha256()
        else:
            hasher = hashlib.md5()

        with open(full_path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                hasher.update(chunk)

        return (full_path, hasher.hexdigest())
    except (PermissionError, FileNotFoundError, OSError) as e:
        logger.warning("无法读取文件进行哈希计算: %s, 错误: %s", full_path, e)
        return (full_path, None)


def find_duplicates(file_infos, shared_folder_name, algorithm="md5", max_workers=4, progress_callback=None):
    """
    查找重复文件组。

    采用多阶段检测流程：
    第一阶段（size_grouping）：按文件大小分组，过滤掉大小唯一的文件。
    第二阶段（hashing）：对同大小组内的候选文件并行计算哈希值。
    第三阶段（done）：将哈希值相同的文件归为一组重复文件。

    Args:
        file_infos: 由扫描器产生的文件信息列表，每个元素为 (full_path, filename, size, mtime_str)
        shared_folder_name: 关联的共享文件夹名称，用于标识结果数据的来源
        algorithm: 哈希算法，"md5" 或 "sha256"，默认 "md5"
        max_workers: 并行计算哈希值的最大线程数，默认 4
        progress_callback: 进度回调函数，签名为 callable(stage, current, total)
                           stage 取值为 "size_grouping"、"hashing"、"done"

    Returns:
        list: 重复文件组列表，每个元素为 (group_id, shared_folder, md5_hex, file_list)
              其中 file_list 为 [(full_path, filename, size, mtime_str), ...]
    """
    algorithm = algorithm.lower()
    if algorithm not in ("md5", "sha256"):
        raise ValueError(f"不支持的哈希算法: {algorithm}，请使用 'md5' 或 'sha256'")

    logger.info("开始重复文件检测，算法: %s，原始文件数: %d", algorithm, len(file_infos))

    # 第一阶段：按文件大小分组
    if progress_callback:
        try:
            progress_callback("size_grouping", 0, len(file_infos))
        except Exception:
            pass

    size_groups = defaultdict(list)
    for file_info in file_infos:
        size_groups[file_info[2]].append(file_info)

    # 过滤掉大小唯一的文件
    candidate_groups = {
        size: files for size, files in size_groups.items() if len(files) > 1
    }

    if progress_callback:
        try:
            progress_callback("size_grouping", len(size_groups), len(size_groups))
        except Exception:
            pass

    logger.info(
        "第一阶段完成：%d 个大小组，其中 %d 组含有多个文件",
        len(size_groups),
        len(candidate_groups),
    )

    if not candidate_groups:
        logger.info("没有大小相同文件组，无需进一步检测")
        if progress_callback:
            try:
                progress_callback("done", 0, 0)
            except Exception:
                pass
        return []

    # 第二阶段：对候选文件并行计算哈希值
    hash_tasks = []
    for files in candidate_groups.values():
        for file_info in files:
            hash_tasks.append(file_info)

    total_hash_tasks = len(hash_tasks)
    completed = 0

    if progress_callback:
        try:
            progress_callback("hashing", 0, total_hash_tasks)
        except Exception:
            pass

    hash_results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_compute_hash, task[0], algorithm): task[0]
            for task in hash_tasks
        }
        for future in futures:
            full_path, hex_digest = future.result()
            if hex_digest is not None:
                hash_results[full_path] = hex_digest
            completed += 1
            if progress_callback and completed % 10 == 0:
                try:
                    progress_callback("hashing", completed, total_hash_tasks)
                except Exception:
                    pass

    if progress_callback:
        try:
            progress_callback("hashing", total_hash_tasks, total_hash_tasks)
        except Exception:
            pass

    logger.info("第二阶段完成：成功计算 %d/%d 个文件的哈希值", len(hash_results), total_hash_tasks)

    # 第三阶段：按哈希值分组，找出重复文件
    hash_groups = defaultdict(list)
    for files in candidate_groups.values():
        group_hashes = defaultdict(list)
        for file_info in files:
            hex_digest = hash_results.get(file_info[0])
            if hex_digest is not None:
                group_hashes[hex_digest].append(file_info)

        for hex_digest, dup_files in group_hashes.items():
            if len(dup_files) > 1:
                hash_groups[hex_digest].extend(dup_files)

    result = []
    for group_id, (md5_hex, dup_files) in enumerate(
        sorted(hash_groups.items()), start=1
    ):
        result.append((group_id, shared_folder_name, md5_hex, dup_files))

    if progress_callback:
        try:
            progress_callback("done", len(result), len(result))
        except Exception:
            pass

    logger.info("检测完成：共发现 %d 组重复文件", len(result))
    return result
