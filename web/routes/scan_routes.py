"""
扫描任务管理路由
==============
提供文件扫描任务的启动、查询、停止和结果获取功能。
扫描任务在后台线程中运行，支持实时进度报告和取消操作。
"""

import datetime
import logging
import threading
from uuid import uuid4

from flask import Blueprint, request, jsonify

from core.scanner import scan_directory
from core.detector import find_duplicates

logger = logging.getLogger("web.routes.scan")

scan_bp = Blueprint("scan", __name__)

_tasks = {}
_tasks_lock = threading.Lock()
_next_task_id = 0


def _generate_task_id():
    """
    生成唯一的任务 ID。

    使用自增整数加短 UUID 的方式保证唯一性。

    Returns:
        str: 格式为 "{auto_increment}_{short_uuid}" 的任务 ID
    """
    global _next_task_id
    with _tasks_lock:
        _next_task_id += 1
        short_uid = uuid4().hex[:6]
        return f"{_next_task_id}_{short_uid}"


def _build_task_record(task_id, directory, min_size, exclude_patterns, algorithm):
    """
    构建任务记录的初始数据结构。

    Args:
        task_id: 任务 ID
        directory: 扫描目录路径
        min_size: 最小文件大小阈值
        exclude_patterns: 排除模式列表
        algorithm: 哈希算法名称

    Returns:
        dict: 任务记录字典
    """
    return {
        "task_id": task_id,
        "status": "pending",
        "directory": directory,
        "min_size": min_size,
        "exclude_patterns": exclude_patterns,
        "algorithm": algorithm,
        "file_count": 0,
        "started_at": None,
        "completed_at": None,
        "progress": {
            "stage": "idle",
            "current": 0,
            "total": 0,
            "percentage": 0,
        },
        "result": None,
        "error": None,
        "cancel_event": threading.Event(),
        "thread": None,
    }


def _run_scan_task(task_id):
    """
    在后台线程中执行扫描任务。

    执行流程：
    1. 扫描目录，收集文件元数据
    2. 对候选文件进行重复检测
    3. 格式化结果并更新任务状态

    任务可能的状态转换：
    pending -> running -> completed
    pending -> running -> failed
    pending -> running -> stopped

    Args:
        task_id: 要执行的任务 ID
    """
    task = _tasks.get(task_id)
    if task is None:
        return

    task["status"] = "running"
    task["started_at"] = datetime.datetime.now().isoformat()

    try:
        scan_progress = _make_scan_progress_callback(task)
        file_infos = scan_directory(
            root_dir=task["directory"],
            min_size=task["min_size"],
            exclude_patterns=task["exclude_patterns"],
            progress_callback=scan_progress,
        )

        if task["cancel_event"].is_set():
            task["status"] = "stopped"
            task["completed_at"] = datetime.datetime.now().isoformat()
            logger.info("扫描任务 %s 已被用户取消", task_id)
            return

        task["file_count"] = len(file_infos)
        logger.info("扫描任务 %s: 目录扫描完成，共 %d 个文件", task_id, len(file_infos))

        detect_progress = _make_detect_progress_callback(task)
        dup_groups = find_duplicates(
            file_infos=file_infos,
            shared_folder_name=task["directory"],
            algorithm=task["algorithm"],
            progress_callback=detect_progress,
        )

        if task["cancel_event"].is_set():
            task["status"] = "stopped"
            task["completed_at"] = datetime.datetime.now().isoformat()
            logger.info("扫描任务 %s 在检测阶段被用户取消", task_id)
            return

        result = _format_dup_groups(dup_groups)
        task["result"] = result
        task["status"] = "completed"
        task["completed_at"] = datetime.datetime.now().isoformat()

        total_groups = len(result)
        total_dups = sum(len(g["files"]) for g in result)
        logger.info(
            "扫描任务 %s 完成: %d 组重复文件，共 %d 个重复文件",
            task_id, total_groups, total_dups,
        )

    except ValueError as e:
        task["status"] = "failed"
        task["error"] = str(e)
        task["completed_at"] = datetime.datetime.now().isoformat()
        logger.error("扫描任务 %s 参数错误: %s", task_id, e)

    except Exception:
        task["status"] = "failed"
        task["error"] = "扫描过程中发生未知错误，请查看日志了解详情"
        task["completed_at"] = datetime.datetime.now().isoformat()
        logger.exception("扫描任务 %s 执行失败", task_id)


def _make_scan_progress_callback(task):
    """
    创建扫描阶段的进度回调函数。

    回调签名为 callable(current, total, current_path)，
    由 core.scanner.scan_directory 调用。

    Args:
        task: 任务记录字典

    Returns:
        callable: 进度回调函数
    """
    def callback(current, total, current_path):
        percentage = round(current / max(total, 1) * 50, 1)
        task["progress"] = {
            "stage": "scanning",
            "current": current,
            "total": total,
            "percentage": min(percentage, 50.0),
            "current_file": current_path,
        }
    return callback


def _make_detect_progress_callback(task):
    """
    创建重复检测阶段的进度回调函数。

    回调签名为 callable(stage, current, total)，
    由 core.detector.find_duplicates 调用。
    stage 取值为 "size_grouping"、"hashing"、"done"。

    Args:
        task: 任务记录字典

    Returns:
        callable: 进度回调函数
    """
    def callback(stage, current, total):
        if stage == "size_grouping":
            percentage = 50.0
        elif stage == "hashing":
            percentage = 50.0 + round(current / max(total, 1) * 45, 1)
        else:
            percentage = 100.0
        task["progress"] = {
            "stage": stage,
            "current": current,
            "total": total,
            "percentage": min(percentage, 100.0),
        }
    return callback


def _format_dup_groups(dup_groups):
    """
    将检测器返回的重复组列表格式化为 JSON 友好的结构。

    Args:
        dup_groups: find_duplicates 返回的列表，
                    每项为 (group_id, shared_folder, md5_hex, file_list)

    Returns:
        list[dict]: 格式化后的重复组列表
    """
    result = []
    for group_id, shared_folder, md5_hex, file_list in dup_groups:
        files = [
            {
                "path": fp,
                "filename": fn,
                "size": s,
                "mtime": mt,
            }
            for fp, fn, s, mt in file_list
        ]
        result.append({
            "group_id": group_id,
            "shared_folder": shared_folder,
            "md5": md5_hex,
            "files": files,
        })
    return result


def _compute_summary(result):
    """
    根据扫描结果计算汇总统计信息。

    Args:
        result: _format_dup_groups 返回的格式化结果列表

    Returns:
        dict: 包含 total_files, total_groups, total_duplicates 的汇总字典
    """
    if not result:
        return {
            "total_files": 0,
            "total_groups": 0,
            "total_duplicates": 0,
        }

    total_groups = len(result)
    total_dups = sum(len(g["files"]) for g in result)
    unique_paths = set()
    for g in result:
        for f in g["files"]:
            unique_paths.add(f["path"])
    total_files = len(unique_paths)

    return {
        "total_files": total_files,
        "total_groups": total_groups,
        "total_duplicates": total_dups,
    }


def _task_to_brief(task):
    """
    将任务记录提取为简要信息，用于任务列表展示。

    Args:
        task: 任务记录字典

    Returns:
        dict: 简要任务信息
    """
    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "directory": task["directory"],
        "file_count": task["file_count"],
        "started_at": task["started_at"],
        "completed_at": task["completed_at"],
        "error": task["error"],
    }


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------


@scan_bp.route('/start', methods=['POST'])
def start_scan():
    """
    启动一个新的扫描任务。

    请求体 (JSON):
        directory (str): 必填，要扫描的目录路径
        min_size (int): 可选，最小文件大小（字节），默认 0
        exclude_patterns (list[str]): 可选，排除的 glob 模式列表
        algorithm (str): 可选，哈希算法 "md5" 或 "sha256"，默认 "md5"

    返回:
        201: {"task_id": str, "status": "started"}
        400: {"error": str} 请求参数无效
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请提供 JSON 请求体"}), 400

    directory = data.get("directory", "").strip()
    if not directory:
        return jsonify({"error": "请提供有效的扫描目录路径"}), 400

    min_size = int(data.get("min_size", 0))
    if min_size < 0:
        min_size = 0

    exclude_patterns = data.get("exclude_patterns", [])
    if not isinstance(exclude_patterns, list):
        exclude_patterns = []

    algorithm = data.get("algorithm", "md5").lower()
    if algorithm not in ("md5", "sha256"):
        return jsonify({"error": f"不支持的哈希算法: {algorithm}，请使用 'md5' 或 'sha256'"}), 400

    task_id = _generate_task_id()
    task = _build_task_record(task_id, directory, min_size, exclude_patterns, algorithm)

    with _tasks_lock:
        _tasks[task_id] = task

    thread = threading.Thread(
        target=_run_scan_task,
        args=(task_id,),
        daemon=True,
        name=f"scan-{task_id}",
    )
    task["thread"] = thread
    thread.start()

    logger.info(
        "扫描任务已启动: %s, 目录: %s, 算法: %s",
        task_id, directory, algorithm,
    )
    return jsonify({"task_id": task_id, "status": "started"}), 201


@scan_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """
    列出所有扫描任务（活跃的和最近完成的）。

    返回:
        200: [{"task_id": str, "status": str, "directory": str, ...}, ...]
    """
    with _tasks_lock:
        task_list = [_task_to_brief(t) for t in _tasks.values()]

    task_list.sort(key=lambda t: t.get("started_at") or "", reverse=True)
    return jsonify(task_list), 200


@scan_bp.route('/status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """
    获取指定扫描任务的详细状态和进度信息。

    Args:
        task_id: 任务 ID

    返回:
        200: {"task_id": str, "status": str, "progress": {...}, "error": null|str}
        404: {"error": str} 任务不存在
    """
    task = _tasks.get(task_id)
    if task is None:
        return jsonify({"error": f"任务不存在: {task_id}"}), 404

    response = {
        "task_id": task["task_id"],
        "status": task["status"],
        "progress": dict(task["progress"]),
        "error": task["error"],
    }

    if task["status"] in ("completed", "failed", "stopped"):
        response["result_summary"] = (
            _compute_summary(task["result"]) if task["result"] else None
        )

    return jsonify(response), 200


@scan_bp.route('/stop/<task_id>', methods=['POST'])
def stop_task(task_id):
    """
    停止一个正在运行的扫描任务。

    通过设置取消事件标志来通知后台线程终止。
    注意：取消操作不是即时的，正在进行的文件 I/O 操作会先完成。

    Args:
        task_id: 任务 ID

    返回:
        200: {"success": true}
        404: {"error": str} 任务不存在
        409: {"error": str, "status": str} 任务不在运行状态
    """
    task = _tasks.get(task_id)
    if task is None:
        return jsonify({"error": f"任务不存在: {task_id}"}), 404

    if task["status"] not in ("running", "pending"):
        return jsonify({
            "error": "任务不在运行状态，无法取消",
            "status": task["status"],
        }), 409

    task["cancel_event"].set()
    logger.info("扫描任务 %s 已请求取消", task_id)
    return jsonify({"success": True}), 200


@scan_bp.route('/result/<task_id>', methods=['GET'])
def get_task_result(task_id):
    """
    获取已完成任务的完整扫描结果。

    Args:
        task_id: 任务 ID

    返回:
        200: {"task_id": str, "shared_folder": str, "dup_groups": [...], "summary": {...}}
        404: {"error": str} 任务不存在
        409: {"error": str, "status": str} 任务尚未完成
    """
    task = _tasks.get(task_id)
    if task is None:
        return jsonify({"error": f"任务不存在: {task_id}"}), 404

    if task["status"] == "failed":
        return jsonify({
            "error": "任务执行失败",
            "status": task["status"],
            "detail": task.get("error"),
        }), 409

    if task["status"] != "completed":
        return jsonify({
            "error": "任务尚未完成",
            "status": task["status"],
            "progress": task["progress"],
        }), 409

    result = task["result"] or []
    summary = _compute_summary(result)

    return jsonify({
        "task_id": task_id,
        "shared_folder": task["directory"],
        "dup_groups": result,
        "summary": summary,
    }), 200
