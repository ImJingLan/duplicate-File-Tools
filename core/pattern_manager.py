"""
受保护文件模式管理器
====================
提供文件保护模式的增删改查、持久化存储、正则校验与路径匹配功能。
"""
import re
import json
import logging
from pathlib import Path

from config.settings import PATTERNS_FILE

logger = logging.getLogger("core.pattern_manager")


class PatternManager:
    """受保护文件模式管理器"""

    def __init__(self, patterns_file=None):
        """
        初始化模式管理器

        Args:
            patterns_file: 自定义模式文件路径，默认使用 config.settings.PATTERNS_FILE
        """
        self._patterns_file = Path(patterns_file) if patterns_file else PATTERNS_FILE
        self._patterns = []
        self._compiled_patterns = []

    def load(self):
        """
        从 JSON 文件加载模式列表

        Returns:
            list[dict]: 模式字典列表，每项包含 pattern/name/enabled
        """
        if not self._patterns_file.exists():
            logger.warning("模式文件不存在: %s，将使用空列表", self._patterns_file)
            self._patterns = []
            self._compile_patterns()
            return []

        try:
            with open(self._patterns_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, list):
                logger.error("模式文件格式错误，应为 JSON 数组")
                self._patterns = []
                self._compile_patterns()
                return []

            self._patterns = []
            for idx, item in enumerate(raw):
                if not isinstance(item, dict):
                    logger.warning("第 %d 项不是字典对象，已跳过", idx + 1)
                    continue
                entry = {
                    "pattern": item.get("pattern", ""),
                    "name": item.get("name", ""),
                    "enabled": bool(item.get("enabled", True)),
                }
                is_valid, err_msg = self.validate_regex(entry["pattern"])
                if not is_valid:
                    logger.warning("模式 '%s' 的正则无效: %s，已禁用", entry["name"], err_msg)
                    entry["enabled"] = False
                self._patterns.append(entry)

            self._compile_patterns()
            logger.info("已加载 %d 条模式，其中 %d 条已启用", len(self._patterns), len(self._compiled_patterns))
            return list(self._patterns)
        except (json.JSONDecodeError, IOError) as e:
            logger.error("加载模式文件失败: %s", e)
            self._patterns = []
            self._compile_patterns()
            return []

    def save(self, patterns=None):
        """
        保存模式列表到 JSON 文件

        Args:
            patterns: 要保存的模式列表，为 None 时保存当前内部列表
        """
        if patterns is not None:
            self._patterns = list(patterns)
            self._compile_patterns()

        self._patterns_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._patterns_file, "w", encoding="utf-8") as f:
            json.dump(self._patterns, f, ensure_ascii=False, indent=2)
        logger.info("已保存 %d 条模式到 %s", len(self._patterns), self._patterns_file)

    def _compile_patterns(self):
        """编译所有已启用的正则模式"""
        self._compiled_patterns = []
        for entry in self._patterns:
            if entry["enabled"]:
                try:
                    compiled = re.compile(entry["pattern"])
                    self._compiled_patterns.append((compiled, entry["name"], entry["pattern"]))
                except re.error:
                    logger.warning("无法编译已启用模式 '%s': %s", entry["name"], entry["pattern"])

    def get_all(self):
        """
        获取所有模式（含启用状态）

        Returns:
            list[dict]: 所有模式条目
        """
        return list(self._patterns)

    def get_enabled(self):
        """
        获取所有已启用的模式

        Returns:
            list[tuple]: (compiled_regex, name, pattern_str) 列表
        """
        return list(self._compiled_patterns)

    def add(self, pattern_str, name, enabled=True):
        """
        添加新模式

        Args:
            pattern_str: 正则表达式字符串
            name: 模式名称/描述
            enabled: 是否启用

        Returns:
            tuple: (success: bool, error_msg: str) — 成功时 error_msg 为空字符串
        """
        is_valid, err_msg = self.validate_regex(pattern_str)
        if not is_valid:
            return False, err_msg

        entry = {
            "pattern": pattern_str,
            "name": name,
            "enabled": bool(enabled),
        }
        self._patterns.append(entry)
        if enabled:
            try:
                compiled = re.compile(pattern_str)
                self._compiled_patterns.append((compiled, name, pattern_str))
            except re.error:
                pass
        logger.info("已添加模式: %s (%s)", name, pattern_str)
        return True, ""

    def update(self, index, pattern_str=None, name=None, enabled=None):
        """
        更新指定位置的模式

        Args:
            index: 模式索引
            pattern_str: 新的正则字符串（为 None 则不更新）
            name: 新的名称（为 None 则不更新）
            enabled: 新的启用状态（为 None 则不更新）

        Returns:
            tuple: (success: bool, error_msg: str)
        """
        if index < 0 or index >= len(self._patterns):
            return False, f"索引 {index} 超出范围 (0~{len(self._patterns) - 1})"

        if pattern_str is not None:
            is_valid, err_msg = self.validate_regex(pattern_str)
            if not is_valid:
                return False, err_msg
            self._patterns[index]["pattern"] = pattern_str

        if name is not None:
            self._patterns[index]["name"] = name

        if enabled is not None:
            self._patterns[index]["enabled"] = bool(enabled)

        self._compile_patterns()
        logger.info("已更新模式 [%d]: %s", index, self._patterns[index]["name"])
        return True, ""

    def delete(self, index):
        """
        删除指定位置的模式

        Args:
            index: 模式索引

        Returns:
            tuple: (success: bool, error_msg: str)
        """
        if index < 0 or index >= len(self._patterns):
            return False, f"索引 {index} 超出范围 (0~{len(self._patterns) - 1})"

        removed = self._patterns.pop(index)
        self._compile_patterns()
        logger.info("已删除模式: %s (%s)", removed["name"], removed["pattern"])
        return True, ""

    def move(self, from_index, to_index):
        """
        移动模式位置

        Args:
            from_index: 源索引
            to_index: 目标索引

        Returns:
            tuple: (success: bool, error_msg: str)
        """
        n = len(self._patterns)
        if from_index < 0 or from_index >= n:
            return False, f"源索引 {from_index} 超出范围 (0~{n - 1})"
        if to_index < 0 or to_index >= n:
            return False, f"目标索引 {to_index} 超出范围 (0~{n - 1})"

        if from_index == to_index:
            return True, ""

        item = self._patterns.pop(from_index)
        self._patterns.insert(to_index, item)
        self._compile_patterns()
        logger.info("已将模式从 %d 移动到 %d", from_index, to_index)
        return True, ""

    def test_match(self, path):
        """
        用所有已启用模式测试路径是否匹配

        Args:
            path: 文件路径字符串

        Returns:
            list[dict]: 匹配的模式信息列表，每项包含 pattern/name
        """
        matches = []
        for compiled, name, pattern_str in self._compiled_patterns:
            if compiled.search(path):
                matches.append({
                    "pattern": pattern_str,
                    "name": name,
                })
        return matches

    def is_protected(self, path):
        """
        检查路径是否受保护

        Args:
            path: 文件路径字符串

        Returns:
            tuple: (is_protected: bool, category_name: str)
        """
        matches = self.test_match(path)
        if matches:
            return True, matches[0]["name"]
        return False, ""

    def validate_regex(self, pattern_str):
        """
        校验正则表达式字符串

        Args:
            pattern_str: 正则表达式字符串

        Returns:
            tuple: (is_valid: bool, error_msg: str)
        """
        try:
            re.compile(pattern_str)
            return True, ""
        except re.error as e:
            return False, str(e)
