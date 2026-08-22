#!/usr/bin/env python3
"""
复杂度重构脚本 - 降低代码圈复杂度

目标：将所有函数的圈复杂度从 >10 降低到 <=8

重构策略：
1. 提取子函数（Extract Method）
2. 早期返回（Early Return）
3. 策略模式（Strategy Pattern）
4. 查找表（Lookup Tables）
"""

import json
import subprocess
import sys
from pathlib import Path


def get_complexity_issues():
    """获取所有复杂度问题"""
    result = subprocess.run(
        ["ruff", "check", "app/agents", "--select=C901", "--output-format=json"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        return []

    try:
        issues = json.loads(result.stdout)
        return sorted(issues, key=lambda x: int(x['message'].split('(')[1].split('>')[0]), reverse=True)
    except Exception as e:
        print(f"解析错误: {e}")
        return []


def print_complexity_report(issues):
    """打印复杂度报告"""
    print("=" * 80)
    print("复杂度重构报告")
    print("=" * 80)
    print(f"\n发现 {len(issues)} 个复杂度过高的函数\n")

    for i, issue in enumerate(issues, 1):
        filename = Path(issue['filename']).relative_to(Path.cwd())
        func_name = issue['message'].split('`')[1]
        complexity = issue['message'].split('(')[1].split('>')[0]
        line = issue['location']['row']

        print(f"{i}. {func_name}() - 复杂度 {complexity}")
        print(f"   📁 {filename}:{line}")
        print(f"   🔗 {issue['url']}\n")


def create_refactor_checklist(issues):
    """创建重构清单"""
    output = ["# 复杂度重构清单\n"]
    output.append("按复杂度从高到低排序\n")

    for i, issue in enumerate(issues, 1):
        filename = Path(issue['filename']).relative_to(Path.cwd())
        func_name = issue['message'].split('`')[1]
        complexity = issue['message'].split('(')[1].split('>')[0]
        line = issue['location']['row']

        output.append(f"\n## {i}. {func_name}() (复杂度: {complexity})")
        output.append(f"**位置**: `{filename}:{line}`\n")
        output.append("**重构策略**:")

        # 根据复杂度推荐策略
        complexity_num = int(complexity)
        if complexity_num >= 20:
            output.append("- [ ] 严重：拆分为多个小函数（目标复杂度 <= 8）")
            output.append("- [ ] 考虑使用策略模式或状态机")
            output.append("- [ ] 提取配置到查找表")
        elif complexity_num >= 15:
            output.append("- [ ] 中等：提取3-4个子函数")
            output.append("- [ ] 使用早期返回减少嵌套")
        else:
            output.append("- [ ] 轻度：提取1-2个子函数")
            output.append("- [ ] 简化条件逻辑")

        output.append("\n**重构状态**: ⬜ 未开始\n")

    return "\n".join(output)


def main():
    print("🔍 扫描复杂度问题...\n")
    issues = get_complexity_issues()

    if not issues:
        print("✅ 没有发现复杂度问题！")
        return 0

    print_complexity_report(issues)

    # 生成清单
    checklist = create_refactor_checklist(issues)
    checklist_path = Path("COMPLEXITY_REFACTOR_CHECKLIST.md")
    checklist_path.write_text(checklist, encoding="utf-8")

    print("=" * 80)
    print(f"📝 重构清单已生成: {checklist_path}")
    print("=" * 80)

    # 统计
    total = len(issues)
    critical = sum(1 for i in issues if int(i['message'].split('(')[1].split('>')[0]) >= 20)
    high = sum(1 for i in issues if 15 <= int(i['message'].split('(')[1].split('>')[0]) < 20)
    medium = sum(1 for i in issues if int(i['message'].split('(')[1].split('>')[0]) < 15)

    print(f"\n📊 统计:")
    print(f"   🔴 严重 (≥20): {critical}")
    print(f"   🟡 高 (15-19): {high}")
    print(f"   🟢 中 (11-14): {medium}")
    print(f"   📈 总计: {total}")

    print(f"\n💡 建议:")
    print(f"   1. 先重构严重问题（复杂度 ≥20）")
    print(f"   2. 使用 'Extract Method' 重构技术")
    print(f"   3. 每次重构后运行测试验证")
    print(f"   4. 目标：所有函数复杂度 ≤ 8")

    return 1


if __name__ == "__main__":
    sys.exit(main())
