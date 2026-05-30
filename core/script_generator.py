"""
脚本与报告生成器
================
生成 Windows 批处理脚本、Linux Shell 脚本，以及人类可读的分析报告。
"""
import os
import logging
from collections import defaultdict

logger = logging.getLogger("core.script_generator")


def _quote_cmd(s):
    """
    Windows CMD 安全转义

    Args:
        s: 原始字符串

    Returns:
        str: 已转义的字符串
    """
    if not s:
        return '""'
    escaped = s.replace("^", "^^").replace("&", "^&").replace("|", "^|").replace("<", "^<").replace(">", "^>").replace("%", "%%")
    return f'"{escaped}"'


def _quote_sh(s):
    """
    Bash 安全转义（单引号包裹）

    Args:
        s: 原始字符串

    Returns:
        str: 已转义的字符串
    """
    if not s:
        return "''"
    return "'" + s.replace("'", "'\\''") + "'"


def generate_batch_script(analysis_results, staging_dir, report_file):
    """
    生成 Windows 批处理 (.bat) 执行脚本

    Args:
        analysis_results: dedup_engine.analyze_all() 返回的分析结果列表
        staging_dir: 暂存目录路径
        report_file: 报告文件路径

    Returns:
        str: 批处理脚本内容
    """
    staging_dir_esc = staging_dir.replace("%", "%%")
    report_file_esc = report_file.replace("%", "%%")

    lines = [
        "@echo off",
        "chcp 65001 >nul",
        "setlocal enabledelayedexpansion",
        "rem ============================================================",
        "rem 智能去重执行脚本 (Windows - 自动生成)",
        "rem 已自动跳过受保护的游戏/程序依赖文件",
        "rem ============================================================",
        "",
        f'set "STAGING_DIR={staging_dir_esc}"',
        f'set "REPORT_FILE={report_file_esc}"',
        "",
        'if not exist "%STAGING_DIR%" mkdir "%STAGING_DIR%"',
        "",
        "set TOTAL_GROUPS=0",
        "set SUCCESS_GROUPS=0",
        "set SKIP_GROUPS=0",
        "set FAIL_GROUPS=0",
        "",
        'echo 智能去重执行报告 > "%REPORT_FILE%"',
        'echo 生成时间: %date% %time% >> "%REPORT_FILE%"',
        'echo ======================================== >> "%REPORT_FILE%"',
        'echo. >> "%REPORT_FILE%"',
        "",
    ]

    for idx, result in enumerate(analysis_results, start=1):
        group_id = result["group_id"]
        keep = result.get("keep")
        remove_list = result.get("remove", [])
        skipped = result.get("protected", [])
        is_temp_cleanup = result.get("office_temp_cleanup", False)

        if not remove_list and not skipped:
            continue
        if not remove_list:
            lines.append(f"rem ===== 组 {group_id}: 全部为受保护文件，已跳过 =====")
            lines.append(f'echo [跳过] 组 {group_id}: 全部为受保护文件 >> "%REPORT_FILE%"')
            lines.append("set /a SKIP_GROUPS+=1")
            lines.append("")
            continue

        ref_file = keep if keep is not None else remove_list[0]
        ref_path = ref_file["path"]
        ref_var = "REF" if is_temp_cleanup else "KEEP"
        group_label = f"Group-{group_id}"

        if is_temp_cleanup:
            lines.append(f"rem ===== {group_label}: Office 临时文件，全部删除 =====")
        else:
            lines.append(f"rem ===== {group_label} =====")
        lines.append(f'echo 处理 {group_label}...')
        lines.append("set /a TOTAL_GROUPS+=1")
        lines.append(f'set "{ref_var}={_quote_cmd(ref_path)}"')
        lines.append("")
        lines.append(f'if not exist "!{ref_var}!" (')
        lines.append(f'    echo   [警告] {group_label}: 参照文件不存在 >> "%REPORT_FILE%"')
        lines.append("    set /a SKIP_GROUPS+=1")
        lines.append(") else (")
        lines.append(f'    for /f "tokens=1" %%m in (\'certutil -hashfile "!{ref_var}!" MD5 ^| findstr /v ":\| "\') do set REF_MD5=%%m')
        lines.append("")

        for i, dup in enumerate(remove_list, start=1):
            dup_path = dup["path"]
            dup_basename = os.path.basename(dup_path)
            target_var = f"TGT_{idx}_{i}"

            lines.append(f'    set "DUP{i}={_quote_cmd(dup_path)}"')
            lines.append(f'    if exist "!DUP{i}!" (')
            lines.append(f'        for /f "tokens=1" %%m in (\'certutil -hashfile "!DUP{i}!" MD5 ^| findstr /v ":\| "\') do set DUP{i}_MD5=%%m')
            lines.append(f'        if "!REF_MD5!"=="!DUP{i}_MD5!" (')
            lines.append(f'            set "{target_var}=%STAGING_DIR%\\{group_id}_{i}_{_quote_cmd(dup_basename)}"')
            lines.append(f'            move "!DUP{i}!" "!{target_var}!"')
            lines.append(f'            echo   [移动] !DUP{i}! --^> !{target_var}! >> "%REPORT_FILE%"')
            lines.append("        ) else (")
            lines.append(f'            echo   [跳过] {group_label}: MD5 不一致! >> "%REPORT_FILE%"')
            lines.append("            set /a FAIL_GROUPS+=1")
            lines.append("        )")
            lines.append("    ) else (")
            lines.append(f'        echo   [跳过] {group_label}: 文件不存在 >> "%REPORT_FILE%"')
            lines.append("    )")
            lines.append("")

        for sp in skipped:
            lines.append(f'    echo   [保护] {_quote_cmd(sp["path"])}  ({sp["protect_category"]}) >> "%REPORT_FILE%"')

        if is_temp_cleanup:
            lines.append('    echo   [清理] Office 临时文件已全部移入暂存区 >> "%REPORT_FILE%"')
        else:
            lines.append(f'    echo   [保留] !{ref_var}! >> "%REPORT_FILE%"')
        lines.append("    set /a SUCCESS_GROUPS+=1")
        lines.append(")")
        lines.append("")

    lines.append('echo. >> "%REPORT_FILE%"')
    lines.append('echo ======================================== >> "%REPORT_FILE%"')
    lines.append('echo 执行统计 >> "%REPORT_FILE%"')
    lines.append('echo ======================================== >> "%REPORT_FILE%"')
    lines.append('echo 总处理组数: %TOTAL_GROUPS% >> "%REPORT_FILE%"')
    lines.append('echo 成功处理: %SUCCESS_GROUPS% >> "%REPORT_FILE%"')
    lines.append('echo 跳过组数: %SKIP_GROUPS% >> "%REPORT_FILE%"')
    lines.append('echo 失败组数: %FAIL_GROUPS% >> "%REPORT_FILE%"')
    lines.append('echo. >> "%REPORT_FILE%"')
    lines.append('echo 暂存目录: %STAGING_DIR% >> "%REPORT_FILE%"')
    lines.append('echo 确认无误后执行: rmdir /s /q "%STAGING_DIR%" >> "%REPORT_FILE%"')
    lines.append("")
    lines.append("echo.")
    lines.append("echo ========================================")
    lines.append("echo 智能去重完成!")
    lines.append("echo 总处理组数: %TOTAL_GROUPS%")
    lines.append("echo 成功处理: %SUCCESS_GROUPS%")
    lines.append("echo 跳过组数: %SKIP_GROUPS%")
    lines.append("echo 失败组数: %FAIL_GROUPS%")
    lines.append("echo.")
    lines.append('echo 重复文件已移动到: %STAGING_DIR%')
    lines.append('echo 确认无误后执行: rmdir /s /q "%STAGING_DIR%"')
    lines.append("")
    lines.append("endlocal")

    return "\n".join(lines)


def generate_shell_script(analysis_results, staging_dir, report_file):
    """
    生成 Linux Shell (.sh) 执行脚本

    Args:
        analysis_results: dedup_engine.analyze_all() 返回的分析结果列表
        staging_dir: 暂存目录路径
        report_file: 报告文件路径

    Returns:
        str: Shell 脚本内容
    """
    lines = [
        "#!/bin/bash",
        "# ============================================================",
        "# 智能去重执行脚本 (Linux - 自动生成)",
        "# 已自动跳过受保护的游戏/程序依赖文件",
        "# 执行: bash run.sh",
        "# ============================================================",
        "",
        "set -euo pipefail",
        "",
        f'STAGING_DIR={_quote_sh(staging_dir)}',
        f'REPORT_FILE={_quote_sh(report_file)}',
        "",
        'mkdir -p "$STAGING_DIR"',
        "",
        "TOTAL_GROUPS=0",
        "SUCCESS_GROUPS=0",
        "SKIP_GROUPS=0",
        "FAIL_GROUPS=0",
        "",
        'echo "智能去重执行报告" > "$REPORT_FILE"',
        'echo "生成时间: $(date \'+%Y-%m-%d %H:%M:%S\')" >> "$REPORT_FILE"',
        'echo "========================================" >> "$REPORT_FILE"',
        'echo "" >> "$REPORT_FILE"',
        "",
    ]

    for idx, result in enumerate(analysis_results, start=1):
        group_id = result["group_id"]
        keep = result.get("keep")
        remove_list = result.get("remove", [])
        skipped = result.get("protected", [])
        is_temp_cleanup = result.get("office_temp_cleanup", False)

        if not remove_list and not skipped:
            continue
        if not remove_list:
            lines.append(f"# ===== 组 {group_id}: 全部为受保护文件，已跳过 =====")
            lines.append(f'echo "[跳过] 组 {group_id}: 全部为受保护文件" >> "$REPORT_FILE"')
            lines.append("SKIP_GROUPS=$((SKIP_GROUPS + 1))")
            lines.append("")
            continue

        ref_file = keep if keep is not None else remove_list[0]
        ref_path = ref_file["path"]
        ref_var = "REF" if is_temp_cleanup else "KEEP"
        group_label = f"Group-{group_id}"

        if is_temp_cleanup:
            lines.append(f"# ===== {group_label}: Office 临时文件，全部删除 =====")
        else:
            lines.append(f"# ===== {group_label} =====")
        lines.append(f'echo "处理 {group_label}..."')
        lines.append("TOTAL_GROUPS=$((TOTAL_GROUPS + 1))")
        lines.append(f'{ref_var}={_quote_sh(ref_path)}')
        lines.append("")
        lines.append(f'if [ ! -f "${ref_var}" ]; then')
        lines.append(f'    echo "  [警告] {group_label}: 参照文件不存在: ${ref_var}" >> "$REPORT_FILE"')
        lines.append("    SKIP_GROUPS=$((SKIP_GROUPS + 1))")
        lines.append("else")
        lines.append(f'    REF_MD5=$(md5sum "${ref_var}" | awk \'{{print $1}}\')')
        lines.append("")

        for i, dup in enumerate(remove_list, start=1):
            dup_path = dup["path"]
            dup_basename = os.path.basename(dup_path)
            staging_target = f'"$STAGING_DIR"/{group_id}_{i}_{_quote_sh(dup_basename)}'
            target_var = f"TGT_{idx}_{i}"

            lines.append(f'    DUP{i}={_quote_sh(dup_path)}')
            lines.append(f'    if [ -f "$DUP{i}" ]; then')
            lines.append(f'        DUP{i}_MD5=$(md5sum "$DUP{i}" | awk \'{{print $1}}\')')
            lines.append(f'        if [ "$REF_MD5" = "$DUP{i}_MD5" ]; then')
            lines.append(f'            {target_var}={staging_target}')
            lines.append(f'            mv "$DUP{i}" "${target_var}"')
            lines.append(f'            echo "  [移动] $DUP{i} -> ${target_var}" >> "$REPORT_FILE"')
            lines.append("        else")
            lines.append(f'            echo "  [跳过] {group_label}: MD5 不一致!" >> "$REPORT_FILE"')
            lines.append("            FAIL_GROUPS=$((FAIL_GROUPS + 1))")
            lines.append("        fi")
            lines.append("    else")
            lines.append(f'        echo "  [跳过] {group_label}: 文件不存在" >> "$REPORT_FILE"')
            lines.append("    fi")
            lines.append("")

        for sp in skipped:
            lines.append(f'    echo "  [保护] {_quote_sh(sp["path"])}  ({sp["protect_category"]})" >> "$REPORT_FILE"')

        if is_temp_cleanup:
            lines.append('    echo "  [清理] Office 临时文件已全部移入暂存区" >> "$REPORT_FILE"')
        else:
            lines.append(f'    echo "  [保留] $KEEP" >> "$REPORT_FILE"')
        lines.append("    SUCCESS_GROUPS=$((SUCCESS_GROUPS + 1))")
        lines.append("fi")
        lines.append("")

    lines.append('echo "" >> "$REPORT_FILE"')
    lines.append('echo "========================================" >> "$REPORT_FILE"')
    lines.append('echo "执行统计" >> "$REPORT_FILE"')
    lines.append('echo "========================================" >> "$REPORT_FILE"')
    lines.append('echo "总处理组数: $TOTAL_GROUPS" >> "$REPORT_FILE"')
    lines.append('echo "成功处理: $SUCCESS_GROUPS" >> "$REPORT_FILE"')
    lines.append('echo "跳过组数: $SKIP_GROUPS" >> "$REPORT_FILE"')
    lines.append('echo "失败组数: $FAIL_GROUPS" >> "$REPORT_FILE"')
    lines.append('echo "" >> "$REPORT_FILE"')
    lines.append('echo "暂存目录: $STAGING_DIR" >> "$REPORT_FILE"')
    lines.append('echo "确认无误后执行: rm -rf $STAGING_DIR" >> "$REPORT_FILE"')
    lines.append("")
    lines.append("echo \"\"")
    lines.append("echo \"========================================\"")
    lines.append("echo \"智能去重完成!\"")
    lines.append("echo \"总处理组数: $TOTAL_GROUPS\"")
    lines.append("echo \"成功处理: $SUCCESS_GROUPS\"")
    lines.append("echo \"跳过组数: $SKIP_GROUPS\"")
    lines.append("echo \"失败组数: $FAIL_GROUPS\"")
    lines.append("echo \"\"")
    lines.append("echo \"重复文件已移动到: $STAGING_DIR\"")
    lines.append("echo \"确认无误后执行: rm -rf $STAGING_DIR\"")

    return "\n".join(lines)


def generate_analysis_report(analysis_results, dup_groups):
    """
    生成人类可读的分析报告

    Args:
        analysis_results: dedup_engine.analyze_all() 返回的分析结果列表
        dup_groups: 原始重复组字典，格式为 {group_id: [file_info_dict, ...]}

    Returns:
        str: 分析报告文本
    """
    lines = []
    lines.append("=" * 70)
    lines.append("智能去重分析报告")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"总重复组数: {len(analysis_results)}")
    lines.append("")

    total_remove = sum(len(r.get("remove", [])) for r in analysis_results)
    total_protected = sum(len(r.get("protected", [])) for r in analysis_results)
    total_skip = sum(
        1 for r in analysis_results
        if not r.get("remove") and r.get("protected")
    )
    total_office_temp = sum(1 for r in analysis_results if r.get("office_temp_cleanup"))
    total_office_temp_files = sum(
        len(r.get("remove", [])) for r in analysis_results if r.get("office_temp_cleanup")
    )

    lines.append(f"可清理重复文件: {total_remove}")
    lines.append(f"  其中 Office 临时文件(~$): {total_office_temp_files} 个 (全部删除, 共 {total_office_temp} 组)")
    lines.append(f"受保护文件(不删除): {total_protected}")
    lines.append(f"全部受保护的组(跳过): {total_skip}")
    lines.append("")

    protect_stats = defaultdict(lambda: {"count": 0})
    for r in analysis_results:
        for f in r.get("protected", []):
            cat = f.get("protect_category", "未知")
            protect_stats[cat]["count"] += 1

    if protect_stats:
        lines.append("-" * 50)
        lines.append("受保护文件分类统计:")
        lines.append("-" * 50)
        for cat in sorted(protect_stats.keys()):
            lines.append(f"  {cat}: {protect_stats[cat]['count']} 个文件")

    lines.append("")
    lines.append("-" * 50)
    lines.append("前 100 组决策详情:")
    lines.append("-" * 50)
    lines.append("")

    max_show = 100
    for idx, result in enumerate(analysis_results):
        if idx >= max_show:
            lines.append(f"... 还有 {len(analysis_results) - max_show} 组，详见执行脚本")
            break

        group_id = result["group_id"]
        keep = result.get("keep")
        remove_list = result.get("remove", [])
        skipped = result.get("protected", [])

        group_files = dup_groups.get(group_id, [])
        lines.append(f"--- 组 {group_id} (共 {len(group_files)} 个文件) ---")

        if keep:
            lines.append(f"  ★ 保留:   {keep['path']}  (分数: {keep.get('score', 'N/A'):.3f})")
        elif result.get("office_temp_cleanup") and remove_list:
            lines.append("  🗑 Office 临时文件，全部删除")

        for dup in remove_list:
            lines.append(f"  ✗ 移除:   {dup['path']}  (分数: {dup.get('score', 0):.3f})")

        for sp in skipped:
            lines.append(f"  🛡 保护:   {sp['path']}  ({sp.get('protect_category', '未知')})")

        lines.append("")

    return "\n".join(lines)


def save_script(script_content, output_path):
    """
    保存脚本到文件，在 Linux 上设置可执行权限

    Args:
        script_content: 脚本内容字符串
        output_path: 输出文件路径
    """
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(script_content)

    if os.name != "nt":
        try:
            os.chmod(output_path, 0o755)
        except OSError:
            logger.warning("无法设置脚本可执行权限: %s", output_path)

    logger.info("脚本已保存: %s", output_path)
