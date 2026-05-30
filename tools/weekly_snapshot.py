#!/usr/bin/env python3
"""
周快照版本号生成器
==================
生成格式为 YYwWWx 的周快照版本号：
  - YY: 年份后两位
  - WW: ISO 周数
  - x: 本周内序号（a-z）

用法:
    python tools/weekly_snapshot.py                  # 生成下一个快照版本号
    python tools/weekly_snapshot.py --get-base-tag   # 获取基础标签
    python tools/weekly_snapshot.py --verbose        # 详细输出
"""

import subprocess
import re
import sys
from datetime import date


def call_command(command):
    """执行 shell 命令并返回输出"""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            encoding="utf-8", errors="replace"
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return ""
    except Exception:
        return ""


def get_year_suffix():
    """获取当前年份的后两位"""
    return str(date.today().year)[-2:]


def get_week_number():
    """
    获取当前日期在一年中的 ISO 周数。
    ISO 周数：周一为一周的开始，第一周包含该年的第一个周四。
    """
    today = date.today()
    return today.isocalendar()[1]


def get_weekly_snapshot_tags():
    """获取所有现有的周快照标签"""
    tags_output = call_command("git tag -l")
    if not tags_output:
        return []

    tags = [t for t in tags_output.split("\n") if t]
    weekly_pattern = re.compile(r'^\d{2}w\d{1,2}[a-z]$')
    return sorted(t for t in tags if weekly_pattern.match(t))


def get_snapshots_for_week(year_suffix, week_num):
    """获取指定周的所有快照标签"""
    tags = get_weekly_snapshot_tags()
    week_prefix = f"{year_suffix}w{week_num}"
    return [t for t in tags if t.startswith(week_prefix)]


def get_next_letter(existing_tags):
    """
    获取下一个版本字母。

    根据当周已有的快照标签，返回下一个可用字母（a-z）。
    如果没有现有标签，返回 'a'。
    """
    if not existing_tags:
        return "a"

    letters = []
    for tag in existing_tags:
        m = re.match(r'^\d{2}w\d{1,2}([a-z])$', tag)
        if m:
            letters.append(m.group(1))

    if not letters:
        return "a"

    last_letter = sorted(letters)[-1]
    char_code = ord(last_letter)
    if char_code >= 122:  # 'z'
        raise ValueError("已达到本周最大快照数量 (z)")

    return chr(char_code + 1)


def generate_next_snapshot_version():
    """生成下一个周快照版本号"""
    year_suffix = get_year_suffix()
    week_num = get_week_number()
    week_prefix = f"{year_suffix}w{week_num}"

    existing_tags = get_snapshots_for_week(year_suffix, week_num)
    next_letter = get_next_letter(existing_tags)

    return f"{week_prefix}{next_letter}"


def get_base_tag():
    """
    获取当前周快照的基础标签。
    逻辑：获取最新的任何类型的标签（Release、Pre-release 或快照标签）
    """
    tags_output = call_command("git tag -l --sort=-creatordate")
    if not tags_output:
        return None

    all_tags = [t for t in tags_output.split("\n") if t]
    if all_tags:
        return all_tags[0]

    return None


def main():
    try:
        if "--get-base-tag" in sys.argv:
            base_tag = get_base_tag()
            if base_tag:
                print(base_tag)
            return

        next_version = generate_next_snapshot_version()
        base_tag = get_base_tag()

        print(next_version)

        if "--verbose" in sys.argv:
            year_suffix = get_year_suffix()
            week_num = get_week_number()
            print(f"年份后两位: {year_suffix}", file=sys.stderr)
            print(f"周数: {week_num}", file=sys.stderr)
            print(f"基础标签: {base_tag or '无'}", file=sys.stderr)
            print(f"下一个快照版本: {next_version}", file=sys.stderr)

    except Exception as e:
        print(f"生成周快照版本号失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
