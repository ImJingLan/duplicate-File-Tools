"""
智能去重操作路由
==============
提供重复文件组分析、去重预览、脚本生成、执行去重和脚本保存功能。
基于 DedupEngine 和 PatternManager 实现智能决策。
"""

import os
import shutil
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify

from core.dedup_engine import DedupEngine
from core.pattern_manager import PatternManager
from core.script_generator import (
    generate_batch_script,
    generate_shell_script,
    save_script,
)

logger = logging.getLogger("web.routes.dedup")

dedup_bp = Blueprint("dedup", __name__)

_pattern_manager = PatternManager()
_pattern_manager.load()
logger.info("模式管理器已初始化，已加载 %d 条模式", len(_pattern_manager.get_all()))

_dedup_engine = DedupEngine(_pattern_manager)

SCRIPT_TYPE_MAP = {
    "bat": "bat",
    "sh": "sh",
}


def _get_scan_result(scan_task_id):
    """
    从扫描任务存储中获取已完成任务的扫描结果。

    Args:
        scan_task_id: 扫描任务 ID

    Returns:
        tuple: (result_data, error_response)
               成功时 result_data 为结果 dict，error_response 为 None
               失败时 result_data 为 None，error_response 为 (json, status_code) 元组
    """
    from web.routes.scan_routes import _tasks, _tasks_lock

    with _tasks_lock:
        task = _tasks.get(scan_task_id)

    if task is None:
        return None, (jsonify({"error": f"扫描任务不存在: {scan_task_id}"}), 404)

    if task["status"] == "failed":
        return None, (jsonify({
            "error": "扫描任务执行失败，无法分析",
            "detail": task.get("error"),
        }), 409)

    if task["status"] != "completed":
        return None, (jsonify({
            "error": "扫描任务尚未完成，请等待扫描结束后再分析",
            "status": task["status"],
        }), 409)

    if not task.get("result"):
        return None, (jsonify({"error": "扫描任务无重复文件结果"}), 404)

    return task, None


def _result_to_dup_groups(result):
    """
    将扫描结果字典转换为 DedupEngine 所需的 dup_groups 格式。

    Args:
        result: 格式化后的扫描结果列表

    Returns:
        dict: {group_id: [{"path": str, "filename": str, "size": int, "mtime": str}, ...]}
    """
    dup_groups = {}
    for group in result:
        dup_groups[str(group["group_id"])] = group["files"]
    return dup_groups


def _run_analysis(scan_task_id, mode, path_pattern=None):
    """
    执行去重分析的核心逻辑。

    Args:
        scan_task_id: 扫描任务 ID
        mode: 去重模式
        path_pattern: keep_by_path_pattern 模式的正则表达式

    Returns:
        tuple: (analysis_results, dup_groups, error)
               成功时 error 为 None
               失败时 analysis_results 和 dup_groups 为 None，error 为 (json, status_code)
    """
    task, error = _get_scan_result(scan_task_id)
    if error:
        return None, None, error

    dup_groups = _result_to_dup_groups(task["result"])
    analysis_results = _dedup_engine.analyze_all(
        dup_groups=dup_groups,
        mode=mode,
        path_pattern=path_pattern,
    )
    return analysis_results, dup_groups, None


def _format_analysis_result(result):
    """
    将单个组的分析结果格式化为 JSON 友好的结构。

    Args:
        result: DedupEngine.analyze_group 返回的结果字典

    Returns:
        dict: 格式化后的组分析结果
    """
    keep = result.get("keep")
    return {
        "group_id": result["group_id"],
        "keep": {
            "path": keep["path"],
            "filename": keep.get("filename", ""),
            "size": keep.get("size", 0),
            "mtime": keep.get("mtime", ""),
            "score": keep.get("score", 0),
        } if keep else None,
        "remove": [
            {
                "path": f["path"],
                "filename": f.get("filename", ""),
                "size": f.get("size", 0),
                "mtime": f.get("mtime", ""),
                "score": f.get("score", 0),
            }
            for f in result.get("remove", [])
        ],
        "protected": [
            {
                "path": f["path"],
                "filename": f.get("filename", ""),
                "size": f.get("size", 0),
                "mtime": f.get("mtime", ""),
                "protect_category": f.get("protect_category", "未知"),
            }
            for f in result.get("protected", [])
        ],
        "office_temp_cleanup": result.get("office_temp_cleanup", False),
    }


def _format_analysis_results(analysis_results):
    """
    将所有分析结果格式化为 JSON 友好的结构。

    Args:
        analysis_results: DedupEngine.analyze_all 返回的结果列表

    Returns:
        list[dict]: 格式化后的分析结果列表
    """
    return [_format_analysis_result(r) for r in analysis_results]


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------


@dedup_bp.route('/analyze', methods=['POST'])
def analyze():
    """
    对扫描结果执行去重分析。

    请求体 (JSON):
        scan_task_id (str): 必填，已完成扫描的任务 ID
        mode (str): 可选，去重模式，默认 "keep_best"
                    可选值: keep_best, keep_largest, keep_newest, keep_by_path_pattern
        path_pattern (str): 可选，当 mode 为 keep_by_path_pattern 时的正则表达式

    返回:
        200: {"analysis": [...], "summary": {...}}
        400: 请求参数无效
        404: 扫描任务不存在
        409: 扫描任务未完成或已失败
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请提供 JSON 请求体"}), 400

    scan_task_id = data.get("scan_task_id", "").strip()
    if not scan_task_id:
        return jsonify({"error": "请提供 scan_task_id"}), 400

    mode = data.get("mode", "keep_best")
    valid_modes = ("keep_best", "keep_largest", "keep_newest", "keep_by_path_pattern")
    if mode not in valid_modes:
        return jsonify({
            "error": f"不支持的去重模式: {mode}",
            "valid_modes": list(valid_modes),
        }), 400

    path_pattern = data.get("path_pattern") if mode == "keep_by_path_pattern" else None
    if mode == "keep_by_path_pattern" and not path_pattern:
        return jsonify({"error": "keep_by_path_pattern 模式需要提供 path_pattern 参数"}), 400

    analysis_results, dup_groups, error = _run_analysis(
        scan_task_id, mode, path_pattern,
    )
    if error:
        return error

    formatted = _format_analysis_results(analysis_results)
    summary = _dedup_engine.get_summary(analysis_results)

    logger.info(
        "分析完成: 扫描任务 %s, 模式 %s, %d 组, 可移除 %d 文件, 受保护 %d 文件",
        scan_task_id, mode, summary["total_groups"],
        summary["total_remove_files"], summary["total_protected_files"],
    )

    return jsonify({
        "analysis": formatted,
        "summary": summary,
    }), 200


@dedup_bp.route('/preview', methods=['POST'])
def preview():
    """
    预览去重操作，返回每组文件的详细决策信息。

    与 analyze 接口类似，但返回更详细的逐文件信息，
    方便前端构建确认界面。

    请求体 (JSON):
        scan_task_id (str): 必填
        mode (str): 可选，去重模式
        path_pattern (str): 可选，正则表达式

    返回:
        200: {"preview": [...], "summary": {...}}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请提供 JSON 请求体"}), 400

    scan_task_id = data.get("scan_task_id", "").strip()
    if not scan_task_id:
        return jsonify({"error": "请提供 scan_task_id"}), 400

    mode = data.get("mode", "keep_best")
    valid_modes = ("keep_best", "keep_largest", "keep_newest", "keep_by_path_pattern")
    if mode not in valid_modes:
        return jsonify({
            "error": f"不支持的去重模式: {mode}",
            "valid_modes": list(valid_modes),
        }), 400

    path_pattern = data.get("path_pattern") if mode == "keep_by_path_pattern" else None

    analysis_results, dup_groups, error = _run_analysis(
        scan_task_id, mode, path_pattern,
    )
    if error:
        return error

    formatted = _format_analysis_results(analysis_results)
    summary = _dedup_engine.get_summary(analysis_results)

    return jsonify({
        "preview": formatted,
        "summary": summary,
        "mode": mode,
        "path_pattern": path_pattern,
    }), 200


@dedup_bp.route('/generate-script', methods=['POST'])
def generate_script():
    """
    生成去重执行脚本。

    根据分析结果生成对应平台的批量执行脚本（.bat 或 .sh）。
    脚本会自动跳过受保护文件。

    请求体 (JSON):
        scan_task_id (str): 必填
        mode (str): 可选，去重模式
        staging_dir (str): 可选，暂存目录路径，默认使用配置中的值
        report_file (str): 可选，报告文件路径
        script_type (str): 可选，"bat" 或 "sh"，不指定则根据当前系统自动选择

    返回:
        200: {"script": str, "script_type": str, "report": str}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请提供 JSON 请求体"}), 400

    scan_task_id = data.get("scan_task_id", "").strip()
    if not scan_task_id:
        return jsonify({"error": "请提供 scan_task_id"}), 400

    mode = data.get("mode", "keep_best")
    valid_modes = ("keep_best", "keep_largest", "keep_newest", "keep_by_path_pattern")
    if mode not in valid_modes:
        return jsonify({
            "error": f"不支持的去重模式: {mode}",
            "valid_modes": list(valid_modes),
        }), 400

    path_pattern = data.get("path_pattern") if mode == "keep_by_path_pattern" else None

    from config.settings import DEFAULT_STAGING_DIR, DEFAULT_OUTPUT_DIR

    staging_dir = data.get("staging_dir", DEFAULT_STAGING_DIR)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_report = os.path.join(DEFAULT_OUTPUT_DIR, f"dedup_report_{timestamp}.txt")
    report_file = data.get("report_file", default_report)

    script_type = data.get("script_type", "").lower()
    if script_type and script_type not in ("bat", "sh"):
        return jsonify({
            "error": f"不支持的脚本类型: {script_type}，请使用 'bat' 或 'sh'",
        }), 400
    if not script_type:
        script_type = "bat" if os.name == "nt" else "sh"

    analysis_results, dup_groups, error = _run_analysis(
        scan_task_id, mode, path_pattern,
    )
    if error:
        return error

    summary = _dedup_engine.get_summary(analysis_results)

    if script_type == "bat":
        script_content = generate_batch_script(analysis_results, staging_dir, report_file)
    else:
        script_content = generate_shell_script(analysis_results, staging_dir, report_file)

    logger.info(
        "脚本已生成: 扫描任务 %s, 类型 %s, 大小 %d 字节",
        scan_task_id, script_type, len(script_content),
    )

    return jsonify({
        "script": script_content,
        "script_type": script_type,
        "report": report_file,
        "summary": summary,
    }), 200


@dedup_bp.route('/execute', methods=['POST'])
def execute_dedup():
    """
    直接执行去重操作，将重复文件移动到暂存目录。

    警告：此操作会实际移动文件！请先使用 /preview 确认结果。

    执行逻辑：
    1. 分析扫描结果
    2. 创建暂存目录（如不存在）
    3. 遍历每个重复组，将"移除"列表中的文件移动到暂存目录
    4. 跳过受保护文件
    5. 为移动的文件创建按组分类的子目录以避免文件名冲突

    请求体 (JSON):
        scan_task_id (str): 必填
        mode (str): 可选，去重模式
        staging_dir (str): 可选，暂存目录路径
        path_pattern (str): 可选，正则表达式

    返回:
        200: {"success": true, "moved_count": int, "skipped_count": int,
              "failed_count": int, "staging_dir": str}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请提供 JSON 请求体"}), 400

    scan_task_id = data.get("scan_task_id", "").strip()
    if not scan_task_id:
        return jsonify({"error": "请提供 scan_task_id"}), 400

    mode = data.get("mode", "keep_best")
    valid_modes = ("keep_best", "keep_largest", "keep_newest", "keep_by_path_pattern")
    if mode not in valid_modes:
        return jsonify({
            "error": f"不支持的去重模式: {mode}",
            "valid_modes": list(valid_modes),
        }), 400

    path_pattern = data.get("path_pattern") if mode == "keep_by_path_pattern" else None

    from config.settings import DEFAULT_STAGING_DIR

    staging_dir = data.get("staging_dir", DEFAULT_STAGING_DIR)

    analysis_results, dup_groups, error = _run_analysis(
        scan_task_id, mode, path_pattern,
    )
    if error:
        return error

    os.makedirs(staging_dir, exist_ok=True)

    moved_count = 0
    skipped_count = 0
    failed_count = 0

    for result in analysis_results:
        group_id = result["group_id"]
        remove_list = result.get("remove", [])
        protected_list = result.get("protected", [])

        skipped_count += len(protected_list)

        if not remove_list:
            continue

        group_staging_dir = os.path.join(staging_dir, f"group_{group_id}")
        os.makedirs(group_staging_dir, exist_ok=True)

        for idx, dup in enumerate(remove_list, start=1):
            src_path = dup["path"]
            if not os.path.exists(src_path):
                logger.warning("文件不存在，跳过: %s", src_path)
                skipped_count += 1
                continue

            basename = os.path.basename(src_path)
            name, ext = os.path.splitext(basename)
            dst_name = f"{idx}_{name}{ext}" if name else f"{idx}{ext}"
            dst_path = os.path.join(group_staging_dir, dst_name)

            if os.path.exists(dst_path):
                dst_path = os.path.join(
                    group_staging_dir,
                    f"{idx}_{name}_{datetime.now().strftime('%H%M%S%f')}{ext}",
                )

            try:
                shutil.move(src_path, dst_path)
                moved_count += 1
                logger.debug("已移动: %s -> %s", src_path, dst_path)
            except (PermissionError, OSError, shutil.Error) as e:
                logger.error("移动文件失败: %s, 错误: %s", src_path, e)
                failed_count += 1

    summary = _dedup_engine.get_summary(analysis_results)

    logger.info(
        "去重执行完成: 扫描任务 %s, 移动 %d, 跳过 %d, 失败 %d, 暂存目录: %s",
        scan_task_id, moved_count, skipped_count, failed_count, staging_dir,
    )

    return jsonify({
        "success": True,
        "moved_count": moved_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "staging_dir": staging_dir,
        "summary": summary,
    }), 200


@dedup_bp.route('/save-script', methods=['POST'])
def save_script_to_file():
    """
    将脚本内容保存到指定文件。

    请求体 (JSON):
        script (str): 必填，脚本内容
        script_type (str): 必填，脚本类型 "bat" 或 "sh"
        output_path (str): 必填，输出文件路径

    返回:
        200: {"success": true, "output_path": str}
        400: 请求参数无效
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请提供 JSON 请求体"}), 400

    script = data.get("script", "")
    if not script:
        return jsonify({"error": "请提供 script 内容"}), 400

    script_type = data.get("script_type", "").lower()
    if script_type not in ("bat", "sh"):
        return jsonify({"error": f"不支持的脚本类型: {script_type}，请使用 'bat' 或 'sh'"}), 400

    output_path = data.get("output_path", "").strip()
    if not output_path:
        return jsonify({"error": "请提供 output_path"}), 400

    try:
        save_script(script, output_path)
        logger.info("脚本已保存: %s (类型: %s)", output_path, script_type)
        return jsonify({
            "success": True,
            "output_path": output_path,
        }), 200
    except (IOError, OSError) as e:
        logger.error("保存脚本失败: %s, 错误: %s", output_path, e)
        return jsonify({
            "error": f"保存脚本失败: {e}",
            "output_path": output_path,
        }), 500
