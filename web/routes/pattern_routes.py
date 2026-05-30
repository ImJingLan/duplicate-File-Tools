"""
保护模式管理路由
==============
提供文件保护模式的增删改查 API。
"""

import logging

from flask import Blueprint, request, jsonify

from core.pattern_manager import PatternManager

logger = logging.getLogger("web.routes.pattern")

pattern_bp = Blueprint("pattern", __name__)

_pattern_manager = PatternManager()
_pattern_manager.load()


@pattern_bp.route('', methods=['GET'])
def list_patterns():
    """获取所有保护模式"""
    patterns = _pattern_manager.get_all()
    return jsonify({"patterns": patterns, "total": len(patterns)}), 200


@pattern_bp.route('', methods=['POST'])
def add_pattern():
    """添加新的保护模式"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请提供 JSON 请求体"}), 400

    pattern_str = data.get("pattern", "").strip()
    if not pattern_str:
        return jsonify({"error": "请提供 pattern 字段"}), 400

    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "请提供 name 字段"}), 400

    enabled = data.get("enabled", True)

    success, err_msg = _pattern_manager.add(pattern_str, name, enabled)
    if not success:
        return jsonify({"error": err_msg}), 400

    _pattern_manager.save()
    return jsonify({"success": True, "message": "模式已添加"}), 201


@pattern_bp.route('/<int:index>', methods=['PUT'])
def update_pattern(index):
    """更新指定索引的保护模式"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请提供 JSON 请求体"}), 400

    pattern_str = data.get("pattern")
    name = data.get("name")
    enabled = data.get("enabled")

    success, err_msg = _pattern_manager.update(index, pattern_str, name, enabled)
    if not success:
        return jsonify({"error": err_msg}), 400

    _pattern_manager.save()
    return jsonify({"success": True, "message": "模式已更新"}), 200


@pattern_bp.route('/<int:index>', methods=['DELETE'])
def delete_pattern(index):
    """删除指定索引的保护模式"""
    success, err_msg = _pattern_manager.delete(index)
    if not success:
        return jsonify({"error": err_msg}), 400

    _pattern_manager.save()
    return jsonify({"success": True, "message": "模式已删除"}), 200


@pattern_bp.route('/move', methods=['POST'])
def move_pattern():
    """移动模式位置"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请提供 JSON 请求体"}), 400

    from_index = data.get("from_index")
    to_index = data.get("to_index")

    if from_index is None or to_index is None:
        return jsonify({"error": "请提供 from_index 和 to_index"}), 400

    success, err_msg = _pattern_manager.move(from_index, to_index)
    if not success:
        return jsonify({"error": err_msg}), 400

    _pattern_manager.save()
    return jsonify({"success": True, "message": "模式已移动"}), 200


@pattern_bp.route('/test', methods=['POST'])
def test_pattern():
    """测试路径是否匹配保护模式"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请提供 JSON 请求体"}), 400

    path = data.get("path", "").strip()
    if not path:
        return jsonify({"error": "请提供 path 字段"}), 400

    is_protected, category = _pattern_manager.is_protected(path)
    matches = _pattern_manager.test_match(path)

    return jsonify({
        "path": path,
        "is_protected": is_protected,
        "protect_category": category,
        "matches": matches,
    }), 200
