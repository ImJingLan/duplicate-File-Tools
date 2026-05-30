"""
文件扫描模块

递归扫描目录，收集文件元数据，支持排除规则和进度回调。
"""

import os
import fnmatch
import logging
from datetime import datetime

from config.settings import CHUNK_SIZE

logger = logging.getLogger("core.scanner")


def _count_items(root_dir, exclude_patterns, min_size):
    """
    预计算需要扫描的文件总数，用于进度报告。

    Args:
        root_dir: 扫描根目录路径
        exclude_patterns: 排除模式列表
        min_size: 最小文件大小（字节）

    Returns:
        需要扫描的文件总数
    """
    count = 0
    try:
        for dirpath, dirnames, filenames in os.walk(root_dir):
            dirnames[:] = sorted(dirnames)
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                if not _should_include(full_path, filename, exclude_patterns, min_size):
                    continue
                count += 1
    except PermissionError:
        pass
    return count


def _should_include(full_path, filename, exclude_patterns, min_size):
    """
    判断文件是否应被纳入扫描结果。

    Args:
        full_path: 文件完整路径
        filename: 文件名
        exclude_patterns: 排除模式列表
        min_size: 最小文件大小（字节）

    Returns:
        bool: True 表示应包含该文件
    """
    if min_size > 0:
        try:
            if os.path.getsize(full_path) < min_size:
                return False
        except OSError:
            return False

    if exclude_patterns:
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return False
            if fnmatch.fnmatch(full_path, pattern):
                return False

    return True


def scan_directory(root_dir, min_size=0, exclude_patterns=None, progress_callback=None):
    """
    递归扫描目录，收集文件元数据。

    遍历指定目录及其所有子目录，收集每个文件的基本信息：
    - 完整路径
    - 文件名
    - 文件大小（字节）
    - 修改时间（ISO 格式字符串）

    支持以下特性：
    - 排除匹配 glob 模式的文件（如 *.tmp、*.log）
    - 按最小文件大小过滤
    - 通过回调函数实时报告扫描进度
    - 优雅处理权限错误和不可访问文件

    Args:
        root_dir: 要扫描的根目录路径
        min_size: 最小文件大小（字节），小于此值的文件将被跳过，默认 0 表示不过滤
        exclude_patterns: glob 排除模式列表，例如 ["*.tmp", "*\\node_modules\\*"]
        progress_callback: 进度回调函数，签名为 callable(current, total, current_path)
                           每次处理文件时调用，用于实时 UI 更新

    Returns:
        list: 包含 (full_path, filename, size, mtime_str) 元组的列表

    Raises:
        ValueError: 当 root_dir 不是有效目录时抛出
    """
    if exclude_patterns is None:
        exclude_patterns = []

    root_dir = os.path.abspath(root_dir)
    if not os.path.isdir(root_dir):
        raise ValueError(f"不是有效的目录: {root_dir}")

    logger.info("开始扫描目录: %s", root_dir)
    logger.debug("最小文件大小: %d 字节, 排除模式: %s", min_size, exclude_patterns)

    total_items = _count_items(root_dir, exclude_patterns, min_size)
    logger.info("预估待扫描文件数: %d", total_items)

    results = []
    processed = 0

    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = sorted(dirnames)

        for filename in sorted(filenames):
            full_path = os.path.join(dirpath, filename)

            if not _should_include(full_path, filename, exclude_patterns, min_size):
                continue

            try:
                stat = os.stat(full_path)
                size = stat.st_size
                mtime = stat.st_mtime
                mtime_str = datetime.fromtimestamp(mtime).isoformat()

                results.append((full_path, filename, size, mtime_str))
            except (PermissionError, FileNotFoundError, OSError) as e:
                logger.warning("无法读取文件: %s, 错误: %s", full_path, e)
                continue

            processed += 1
            if progress_callback:
                try:
                    progress_callback(processed, total_items, full_path)
                except Exception:
                    pass

    logger.info("扫描完成，共找到 %d 个文件", len(results))
    return results
