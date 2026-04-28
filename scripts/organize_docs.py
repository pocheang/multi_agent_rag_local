#!/usr/bin/env python3
"""
企业级文档整理脚本
将文档按类型整理到相应的目录中
"""

import os
import shutil
from pathlib import Path
from typing import List, Tuple

# 文档分类配置
DOCS_CONFIG = {
    "archive": [
        "2026-04-26-documentation-update-summary.md",
        "CHANGELOG_2026-04-27.md",
        "DEEP_CODE_REVIEW_2026-04-27.md",
        "DOCUMENTATION_COMPLETENESS_REPORT.md",
        "DOCUMENT_VERSION_CONTROL.md",
        "FINAL_FIXES_SUMMARY_2026-04-27.md",
        "FIXES_INDEX.md",
        "FIXES_ROUND2_2026-04-27.md",
        "FIXES_ROUND3_2026-04-27.md",
        "FIXES_ROUND4_2026-04-27.md",
        "GITHUB_RELEASE_v0.2.5.md",
        "LOGIC_FIXES_2026-04-27.md",
        "LOGIC_FIXES_DETAILED_2026-04-27.md",
        "LOGIC_FIXES_ROUND2_2026-04-27.md",
        "P1_REFACTORING_COMPLETE.md",
        "P1_VERIFICATION_REPORT.md",
        "P2_REFACTORING_COMPLETE.md",
        "README_CN.md",
        "REFACTORING_COMPLETE_v0.3.0.md",
        "REFACTORING_PLAN.md",
        "REFACTORING_RECOMMENDATION.md",
        "RELEASE_CONFIRMATION_v0.2.5.md",
        "RELEASE_SUMMARY_v0.2.5.md",
        "V0.3.0_DOCS_UPDATE.md",
        "V0.3.0_ISSUE_CHECK.md",
        "V0.3.0_STATUS_REPORT.md",
        "claude-api-setup.md",
        "workflow_lowcode_setup.md",
        "如何找到API设置.md",
        "网络功能检查报告.md",
    ],
    "project": [
        "production_readiness_checklist.md",
    ],
    "delete": [
        "GITHUB_RELEASE_GUIDE.md",
    ]
}

def move_file(src: Path, dst: Path) -> bool:
    """移动文件到目标目录"""
    try:
        if not src.exists():
            print(f"⚠️  文件不存在: {src.name}")
            return False

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        print(f"✅ 移动: {src.name} -> {dst.parent.name}/")
        return True
    except Exception as e:
        print(f"❌ 错误: {src.name} - {e}")
        return False

def delete_file(path: Path) -> bool:
    """删除文件"""
    try:
        if not path.exists():
            print(f"⚠️  文件不存在: {path.name}")
            return False

        path.unlink()
        print(f"🗑️  删除: {path.name}")
        return True
    except Exception as e:
        print(f"❌ 错误: {path.name} - {e}")
        return False

def delete_directory(path: Path) -> bool:
    """删除目录"""
    try:
        if not path.exists():
            print(f"⚠️  目录不存在: {path.name}")
            return False

        shutil.rmtree(str(path))
        print(f"🗑️  删除目录: {path.name}")
        return True
    except Exception as e:
        print(f"❌ 错误: {path.name} - {e}")
        return False

def organize_docs(docs_dir: Path) -> None:
    """整理文档"""
    print("=" * 60)
    print("企业级文档整理")
    print("=" * 60)

    # 统计
    stats = {
        "moved": 0,
        "deleted": 0,
        "failed": 0,
    }

    # 移动到 archive
    print("\n📦 移动历史文档到 archive/")
    print("-" * 60)
    for filename in DOCS_CONFIG["archive"]:
        src = docs_dir / filename
        dst = docs_dir / "archive" / filename
        if move_file(src, dst):
            stats["moved"] += 1
        else:
            stats["failed"] += 1

    # 移动到 project
    print("\n📦 移动项目文档到 project/")
    print("-" * 60)
    for filename in DOCS_CONFIG["project"]:
        src = docs_dir / filename
        dst = docs_dir / "project" / filename
        if move_file(src, dst):
            stats["moved"] += 1
        else:
            stats["failed"] += 1

    # 删除无用文档
    print("\n🗑️  删除无用文档")
    print("-" * 60)
    for filename in DOCS_CONFIG["delete"]:
        path = docs_dir / filename
        if delete_file(path):
            stats["deleted"] += 1
        else:
            stats["failed"] += 1

    # 删除 fixes 子目录
    fixes_dir = docs_dir / "fixes"
    if fixes_dir.exists():
        print(f"\n🗑️  删除 fixes/ 子目录")
        if delete_directory(fixes_dir):
            stats["deleted"] += 1
        else:
            stats["failed"] += 1

    # 统计结果
    print("\n" + "=" * 60)
    print("整理完成")
    print("=" * 60)
    print(f"✅ 已移动: {stats['moved']} 个文件")
    print(f"🗑️  已删除: {stats['deleted']} 个文件/目录")
    if stats["failed"] > 0:
        print(f"❌ 失败: {stats['failed']} 个操作")
    print("=" * 60)

if __name__ == "__main__":
    docs_dir = Path(__file__).parent / "docs"
    if not docs_dir.exists():
        print(f"❌ 文档目录不存在: {docs_dir}")
        exit(1)

    organize_docs(docs_dir)
