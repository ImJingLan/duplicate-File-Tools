#!/usr/bin/env python3
"""
变更日志生成器
==============
从 Git 提交历史自动生成结构化的 Markdown 变更日志。
支持约定式提交分类、中文关键词识别、GitHub 链接生成。

用法:
    python tools/generate_changelog.py [选项]

选项:
    --tag, -t <标签>       指定发布标签名称
    --base, --latest, -b <标签>  指定基础标签
    -wh, --with-hash      显示提交哈希
    -wc, --with-commitizen  保留 commitizen 前缀
    --output-only         仅输出 changelog 内容（用于 CI/CD）
    -h, --help            显示帮助信息
"""

import subprocess
import re
import sys
import argparse
from pathlib import Path
from datetime import date

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHANGELOG_PATH = PROJECT_ROOT / "CHANGELOG.md"

TYPE_MAP = {
    "feat":     "新增 | New",
    "fix":      "修复 | Fix",
    "refactor": "改进 | Improved",
    "perf":     "改进 | Improved",
    "rft":      "改进 | Improved",
    "docs":     "文档 | Docs",
    "doc":      "文档 | Docs",
    "style":    "其他 | Other",
    "build":    "其他 | Other",
    "ci":       "自动化 | CI",
    "test":     "其他 | Other",
    "chore":    "其他 | Other",
}

CHINESE_KEYWORDS = {
    "新增": "新增 | New",
    "修复": "修复 | Fix",
    "更新": "改进 | Improved",
    "改进": "改进 | Improved",
    "优化": "改进 | Improved",
    "重构": "改进 | Improved",
    "文档": "文档 | Docs",
}

CATEGORY_ORDER = [
    "新增 | New",
    "修复 | Fix",
    "改进 | Improved",
    "文档 | Docs",
    "自动化 | CI",
    "其他 | Other",
]

IGNORE_PREFIXES = re.compile(r'^(?:build|style|debug)\s*(?:\([^)]*\))*:\s*')


def call_command(command):
    """执行 shell 命令并返回输出"""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            encoding="utf-8", errors="replace"
        )
        if result.returncode == 0:
            return result.stdout.strip()
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                encoding="gbk", errors="replace"
            )
            return result.stdout.strip()
        except Exception:
            return ""
    except Exception:
        return ""


def get_latest_tag():
    """获取最新的 Git 标签（匹配 v* 模式）"""
    output = call_command('git describe --tags --match "v*" --abbrev=0')
    return output if output else None


def get_current_tag():
    """获取当前 HEAD 对应的标签"""
    output = call_command('git describe --tags --match "v*"')
    return output if output else None


def parse_category(message):
    """解析提交消息的分类"""
    if IGNORE_PREFIXES.match(message):
        return None

    m = re.match(r'^(?P<prefix>\w+)(?:\([\w\-]+\))?:\s*', message)
    if m:
        prefix = m.group("prefix").lower()
        return TYPE_MAP.get(prefix, "其他 | Other")

    for keyword, category in CHINESE_KEYWORDS.items():
        if keyword in message:
            return category

    return "其他 | Other"


def get_commits(latest=None):
    """获取指定范围内的 Git 提交记录"""
    if latest:
        git_command = f'git log {latest}..HEAD --pretty=format:"%H%n%aN%n%s"'
    else:
        git_command = 'git log --pretty=format:"%H%n%aN%n%s" -n 50'

    output = call_command(git_command)
    if not output:
        return []

    commits = []
    lines = output.split("\n")

    for i in range(0, len(lines), 3):
        if i + 2 >= len(lines):
            break
        commits.append({
            "hash": lines[i],
            "author": lines[i + 1],
            "message": lines[i + 2],
        })

    return commits


def classify_commits(commits, with_commitizen=False):
    """对提交记录进行分类"""
    categories = {}
    for cat in CATEGORY_ORDER:
        categories[cat] = []

    contributors = set()

    for commit in commits:
        if "[skip changelog]" in commit["message"]:
            continue

        if re.match(r'^chore:\s*update\s+version\s+to\s+.+', commit["message"], re.IGNORECASE):
            continue

        category = parse_category(commit["message"])
        if category is None:
            continue

        message = commit["message"]

        if not with_commitizen:
            message = re.sub(r'^(?P<prefix>\w+)(?:\([\w\-]+\))?:\s*', '', message)

        if commit["author"] and commit["author"] != "web-flow":
            contributors.add(commit["author"])

        categories[category].append({
            "message": message,
            "author": commit["author"],
            "hash": commit["hash"][:8],
        })

    return categories, list(contributors)


def get_github_repo_url():
    """从 git remote 获取 GitHub 仓库 URL"""
    remote_url = call_command("git remote get-url origin")
    if not remote_url:
        return None

    repo_path = remote_url
    if repo_path.startswith("git@"):
        repo_path = repo_path.replace("git@github.com:", "https://github.com/")
    repo_path = repo_path.replace(".git", "")
    return repo_path


def generate_markdown(classified_data, tag_name, latest, with_hash=False):
    """生成 Markdown 格式的变更日志"""
    categories, contributors = classified_data
    today = date.today().strftime("%Y-%m-%d")
    repo_url = get_github_repo_url()
    lines = []

    if tag_name:
        lines.append(f"## {tag_name}")
    else:
        lines.append(f"## 📝 更新日志 ({today})")

    if latest and repo_url:
        end_tag = tag_name or "HEAD"
        lines.append(f"> [{latest}...{end_tag}]({repo_url}/compare/{latest}...{end_tag})")
    elif latest:
        lines.append(f"> {latest} ... HEAD")
    lines.append("")

    for category in CATEGORY_ORDER:
        if not categories.get(category):
            continue

        lines.append(f"### {category}")
        lines.append("")

        for item in categories[category]:
            line = f"* {item['message']}"
            if with_hash and repo_url:
                line += f" ([{item['hash']}]({repo_url}/commit/{item['hash']}))"
            elif with_hash:
                line += f" ({item['hash']})"
            if item["author"] and item["author"] != "web-flow":
                line += f" @{item['author']}"
            lines.append(line)

        lines.append("")

    return "\n".join(lines)


def write_to_file(content, append=False):
    """将内容写入 CHANGELOG.md"""
    try:
        if append:
            with open(CHANGELOG_PATH, "a", encoding="utf-8") as f:
                f.write("\n" + content)
        else:
            with open(CHANGELOG_PATH, "w", encoding="utf-8") as f:
                f.write(content)
    except IOError as e:
        print(f"⚠️  写入 CHANGELOG.md 失败: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="从 Git 提交历史生成结构化的 Markdown 变更日志",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python tools/generate_changelog.py --tag v1.0.0
  python tools/generate_changelog.py --tag v1.0.0 --base v0.9.0 --with-hash
  python tools/generate_changelog.py --output-only --base v0.9.0
        """,
    )
    parser.add_argument("--tag", "-t", default=None, help="发布标签名称")
    parser.add_argument("--base", "--latest", "-b", default=None,
                        help="基础标签（生成此标签之后的变更）")
    parser.add_argument("-wh", "--with-hash", action="store_true",
                        help="在每条记录后显示提交哈希")
    parser.add_argument("-wc", "--with-commitizen", action="store_true",
                        help="保留 commitizen 前缀")
    parser.add_argument("--output-only", action="store_true",
                        help="仅输出到控制台（用于 CI/CD 管道）")

    args = parser.parse_args()

    resolved_latest = args.base or get_latest_tag()
    resolved_tag_name = args.tag or get_current_tag()

    if not args.output_only:
        print("📊 正在生成变更日志...")
        if resolved_latest:
            print(f"📌 从: {resolved_latest}")
        if resolved_tag_name:
            print(f"🏷️  到: {resolved_tag_name}")
        print()

    commits = get_commits(resolved_latest)
    if not commits:
        if not args.output_only:
            print("⚠️  没有找到提交记录")
        return

    categories, contributors = classify_commits(commits, args.with_commitizen)
    markdown = generate_markdown(
        (categories, contributors), resolved_tag_name, resolved_latest, args.with_hash
    )

    write_to_file(markdown, append=bool(resolved_latest))

    if args.output_only:
        print(markdown)
    else:
        print("✅ 变更日志已更新: CHANGELOG.md")
        print()
        print(markdown)


if __name__ == "__main__":
    main()
