"""
历史记录管理路由
==============
提供扫描历史记录的查询和管理功能。
"""

import logging

from flask import Blueprint, jsonify

logger = logging.getLogger("web.routes.history")

history_bp = Blueprint("history", __name__)


@history_bp.route('', methods=['GET'])
def list_history():
    """获取扫描历史记录列表"""
    from web.routes.scan_routes import _tasks, _tasks_lock

    with _tasks_lock:
        history = []
        for task in _tasks.values():
            history.append({
                "task_id": task["task_id"],
                "status": task["status"],
                "directory": task["directory"],
                "file_count": task["file_count"],
                "started_at": task["started_at"],
                "completed_at": task["completed_at"],
                "error": task.get("error"),
            })

    history.sort(key=lambda t: t.get("started_at") or "", reverse=True)
    return jsonify({"history": history, "total": len(history)}), 200


@history_bp.route('/<task_id>', methods=['GET'])
def get_history_detail(task_id):
    """获取指定历史记录的详细信息"""
    from web.routes.scan_routes import _tasks, _tasks_lock

    with _tasks_lock:
        task = _tasks.get(task_id)

    if task is None:
        return jsonify({"error": f"历史记录不存在: {task_id}"}), 404

    result = task.get("result") or []
    num_groups = len(result)
    num_files = sum(len(g["files"]) for g in result)

    return jsonify({
        "task_id": task["task_id"],
        "status": task["status"],
        "directory": task["directory"],
        "file_count": task["file_count"],
        "started_at": task["started_at"],
        "completed_at": task["completed_at"],
        "error": task.get("error"),
        "stats": {
            "duplicate_groups": num_groups,
            "duplicate_files": num_files,
        },
    }), 200


@history_bp.route('/<task_id>', methods=['DELETE'])
def delete_history(task_id):
    """删除指定历史记录"""
    from web.routes.scan_routes import _tasks, _tasks_lock

    with _tasks_lock:
        if task_id not in _tasks:
            return jsonify({"error": f"历史记录不存在: {task_id}"}), 404

        task = _tasks.pop(task_id)
        if task.get("cancel_event"):
            task["cancel_event"].set()

    logger.info("历史记录已删除: %s", task_id)
    return jsonify({"success": True, "message": "历史记录已删除"}), 200
