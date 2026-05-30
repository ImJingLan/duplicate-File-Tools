"""
智能去重决策引擎
================
根据路径评分、文件属性、保护规则等多维度信息，对重复文件组进行智能决策，
确定每组中应保留和应移除的文件。
"""
import os
import re
import logging

logger = logging.getLogger("core.dedup_engine")

BAD_KEYWORDS = [
    ("WindowsTimemachine", -20),
    ("Dataset_2", -10),
    ("MacBack", -15),
    ("Lightroom 备份", -10),
    ("新建文件夹", -15),
    ("Old_2205", -10),
    ("数据盘", -5),
    ("MobileBackup", -5),
    ("OneDrive - Lite Cafe", -5),
]

GOOD_KEYWORDS = [
    ("素材", 8),
    ("movies", 5),
    ("Photos", 5),
    ("Important", 10),
    ("班级资料", 3),
    ("教学资料", 3),
]

TIMESTAMP_SUFFIX_RE = re.compile(r'_\d{14,}')
FILENAME_SUFFIX_PENALTY = -10

COPY_SUFFIX_RE = re.compile(r'\s*\(\d+\)')
COPY_SUFFIX_PENALTY = -12

DEPTH_PENALTY_PER_LEVEL = -2

CACHE_JUNK_PATTERNS = [
    re.compile(r'Media Cache/'),
    re.compile(r'\.pek$'),
    re.compile(r'CacheClip/'),
    re.compile(r'\.gallery/'),
    re.compile(r'-journal$'),
    re.compile(r'/LOCK$'),
    re.compile(r'\.log$'),
]

OFFICE_TEMP_RE = re.compile(r'^~\$')
OFFICE_TEMP_PENALTY = -100


def _is_cache_junk(path):
    """检测路径是否为缓存/垃圾文件"""
    for pattern in CACHE_JUNK_PATTERNS:
        if pattern.search(path):
            return True
    return False


def _is_office_temp(path):
    """检测路径是否为 Office 临时文件"""
    return bool(OFFICE_TEMP_RE.search(os.path.basename(path)))


class DedupEngine:
    """智能去重决策引擎"""

    def __init__(self, pattern_manager):
        """
        初始化决策引擎

        Args:
            pattern_manager: PatternManager 实例，用于受保护文件检测
        """
        self._pm = pattern_manager

    def score_path(self, path, base_prefixes=None):
        """
        对文件路径进行评分，分数越高越值得保留

        Args:
            path: 文件路径字符串
            base_prefixes: 可选的路径前缀列表，评分前先剥离这些前缀

        Returns:
            float: 路径评分
        """
        score = 100.0
        relative = path

        if base_prefixes:
            for prefix in base_prefixes:
                if relative.startswith(prefix):
                    relative = relative[len(prefix):]
                    break

        parts = relative.replace("\\", "/").split("/")
        depth = len(parts)
        score += depth * DEPTH_PENALTY_PER_LEVEL

        for keyword, penalty in BAD_KEYWORDS:
            if keyword.lower() in relative.lower():
                score += penalty

        for keyword, bonus in GOOD_KEYWORDS:
            if keyword.lower() in relative.lower():
                score += bonus

        filename = parts[-1] if parts else ""

        if TIMESTAMP_SUFFIX_RE.search(filename):
            score += FILENAME_SUFFIX_PENALTY

        if COPY_SUFFIX_RE.search(filename):
            score += COPY_SUFFIX_PENALTY

        if _is_cache_junk(relative):
            score -= 10

        if OFFICE_TEMP_RE.search(filename):
            score += OFFICE_TEMP_PENALTY

        score -= len(relative) * 0.001

        return score

    def analyze_group(self, group_id, files_info, mode="keep_best", path_pattern=None):
        """
        分析一个重复文件组，决策保留/移除哪些文件

        Args:
            group_id: 组标识符
            files_info: 文件信息列表，每项为 dict，包含 path/size/mtime 等键
            mode: 去重模式
                  - "keep_best": 保留评分最高的文件
                  - "keep_largest": 保留最大的文件
                  - "keep_newest": 保留最近修改的文件
                  - "keep_by_path_pattern": 保留路径匹配指定正则的文件
            path_pattern: 当 mode 为 "keep_by_path_pattern" 时的正则表达式

        Returns:
            dict: 包含以下键
                group_id: 组标识符
                keep: dict 或 None（要保留的文件信息）
                remove: list[dict]（要移除的文件列表）
                protected: list[dict]（受保护跳过的文件列表）
                office_temp_cleanup: bool（是否整组都是 Office 临时文件）
        """
        if not files_info or len(files_info) < 2:
            return {
                "group_id": group_id,
                "keep": files_info[0] if files_info else None,
                "remove": [],
                "protected": [],
                "office_temp_cleanup": False,
            }

        all_office_temp = all(_is_office_temp(f["path"]) for f in files_info)

        if all_office_temp:
            for f in files_info:
                f["score"] = self.score_path(f["path"])
                f["protected"] = False
            return {
                "group_id": group_id,
                "keep": None,
                "remove": list(files_info),
                "protected": [],
                "office_temp_cleanup": True,
            }

        protected = []
        deletable = []

        for f in files_info:
            is_p, category = self._pm.is_protected(f["path"])
            if is_p:
                f["protected"] = True
                f["protect_category"] = category
                protected.append(f)
            else:
                f["protected"] = False
                f["score"] = self.score_path(f["path"])
                deletable.append(f)

        keep = None
        remove_list = []

        if deletable:
            if mode == "keep_largest":
                deletable.sort(key=lambda x: int(x.get("size", 0)), reverse=True)
            elif mode == "keep_newest":
                deletable.sort(key=lambda x: x.get("mtime", ""), reverse=True)
            elif mode == "keep_by_path_pattern" and path_pattern:
                try:
                    pat = re.compile(path_pattern)
                except re.error:
                    logger.error("keep_by_path_pattern 正则无效: %s，回退为 keep_best", path_pattern)
                    deletable.sort(key=lambda x: x["score"], reverse=True)
                else:
                    keep_candidates = [f for f in deletable if pat.search(f["path"])]
                    other = [f for f in deletable if not pat.search(f["path"])]
                    if keep_candidates:
                        keep_candidates.sort(key=lambda x: x["score"], reverse=True)
                        keep = keep_candidates[0]
                        remove_list = keep_candidates[1:] + other
                    else:
                        deletable.sort(key=lambda x: x["score"], reverse=True)
                        keep = deletable[0] if deletable else None
                        remove_list = deletable[1:]
            else:
                deletable.sort(key=lambda x: x["score"], reverse=True)

            if mode != "keep_by_path_pattern" or not (mode == "keep_by_path_pattern" and path_pattern and keep is not None):
                if deletable:
                    keep = deletable[0]
                    remove_list = deletable[1:]

        return {
            "group_id": group_id,
            "keep": keep,
            "remove": remove_list,
            "protected": protected,
            "office_temp_cleanup": all_office_temp,
        }

    def analyze_all(self, dup_groups, mode="keep_best", base_prefixes=None, path_pattern=None):
        """
        分析所有重复文件组

        Args:
            dup_groups: 重复组字典，格式为 {group_id: [file_info_dict, ...]}
            mode: 去重模式
            base_prefixes: 评分前剥离的路径前缀列表
            path_pattern: keep_by_path_pattern 模式使用的正则

        Returns:
            list[dict]: 分析结果列表，每项为 analyze_group 的返回值
        """
        results = []
        for group_id in sorted(dup_groups.keys(), key=lambda x: int(x) if str(x).isdigit() else str(x)):
            files = dup_groups[group_id]
            if base_prefixes:
                for f in files:
                    relative = f["path"]
                    for prefix in base_prefixes:
                        if relative.startswith(prefix):
                            relative = relative[len(prefix):]
                            break
                    f["score"] = self.score_path(relative)
            result = self.analyze_group(group_id, files, mode=mode, path_pattern=path_pattern)
            results.append(result)

        logger.info(
            "分析完成: %d 组, 可移除 %d 文件, 受保护 %d 文件",
            len(results),
            sum(len(r["remove"]) for r in results),
            sum(len(r["protected"]) for r in results),
        )
        return results

    def get_summary(self, analysis_results):
        """
        获取分析结果汇总统计

        Args:
            analysis_results: analyze_all 返回的结果列表

        Returns:
            dict: 汇总统计信息
        """
        total_groups = len(analysis_results)
        total_remove = sum(len(r["remove"]) for r in analysis_results)
        total_protected = sum(len(r["protected"]) for r in analysis_results)
        total_keep = sum(1 for r in analysis_results if r["keep"] is not None)
        total_office_temp_groups = sum(1 for r in analysis_results if r["office_temp_cleanup"])
        total_office_temp_files = sum(len(r["remove"]) for r in analysis_results if r["office_temp_cleanup"])
        all_protected_groups = sum(
            1 for r in analysis_results
            if r["protected"] and not r["remove"] and not r["office_temp_cleanup"]
        )

        category_stats = {}
        for r in analysis_results:
            for f in r["protected"]:
                cat = f.get("protect_category", "未知")
                category_stats[cat] = category_stats.get(cat, 0) + 1

        return {
            "total_groups": total_groups,
            "total_remove_files": total_remove,
            "total_protected_files": total_protected,
            "total_keep_files": total_keep,
            "office_temp_groups": total_office_temp_groups,
            "office_temp_files": total_office_temp_files,
            "all_protected_groups": all_protected_groups,
            "category_stats": category_stats,
        }
