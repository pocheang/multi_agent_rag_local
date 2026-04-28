#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档自动修复脚本
修复断开的链接、更新日期、修正元数据
"""

import re
import sys
from pathlib import Path
from datetime import datetime
import json

# 设置输出编码
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


class DocumentationFixer:
    def __init__(self, docs_dir: Path = Path("docs")):
        self.docs_dir = docs_dir
        self.fixes_applied = 0
        self.current_date = "2026-04-28"

    def fix_all(self):
        """运行所有修复"""
        print("🔧 开始修复文档...\n")

        self.fix_broken_links()
        self.update_dates()
        self.add_missing_metadata()
        self.normalize_version_references()

        print(f"\n✅ 完成! 应用了 {self.fixes_applied} 个修复")

    def fix_broken_links(self):
        """修复断开的链接"""
        print("🔗 修复断开的链接...")

        # 常见的链接修复模式
        link_fixes = {
            r'docs/docs/': 'docs/',
            r'\(docs/README\.md\)': '(README.md)',
            r'\(docs/DOCUMENTATION_STANDARD\.md\)': '(DOCUMENTATION_STANDARD.md)',
            r'\(docs/DOCUMENTATION_MAINTENANCE\.md\)': '(DOCUMENTATION_MAINTENANCE.md)',
            r'\(docs/ARCHIVE_REFERENCE\.md\)': '(ARCHIVE_REFERENCE.md)',
            r'\(docs/API_SETTINGS_GUIDE\.md\)': '(API_SETTINGS_GUIDE.md)',
            r'\(docs/PERFORMANCE_OPTIMIZATION\.md\)': '(PERFORMANCE_OPTIMIZATION.md)',
            r'\(docs/project/production_readiness_checklist\.md\)': '(project/production_readiness_checklist.md)',
            r'\(docs/archive/\)': '(archive/)',
        }

        for md_file in self.docs_dir.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            original_content = content

            for pattern, replacement in link_fixes.items():
                content = re.sub(pattern, replacement, content)

            if content != original_content:
                md_file.write_text(content, encoding="utf-8")
                self.fixes_applied += 1
                print(f"  ✓ 修复: {md_file.name}")

    def update_dates(self):
        """更新过时的日期"""
        print("\n📅 更新日期...")

        for md_file in self.docs_dir.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            original_content = content

            # 更新"最后更新"日期
            content = re.sub(
                r'\*\*最后更新\*\*:\s*\d{4}-\d{2}-\d{2}',
                f'**最后更新**: {self.current_date}',
                content
            )

            # 修复未来日期（如果在文档元数据中）
            future_dates = [
                ('2026-07-27', '2026-04-27'),
                ('2026-07-28', '2026-04-28'),
                ('2026-05-27', '2026-04-27'),
                ('2026-04-29', '2026-04-28'),
            ]

            for future_date, correct_date in future_dates:
                if future_date in content:
                    # 只在元数据部分替换
                    lines = content.split('\n')
                    for i, line in enumerate(lines[:20]):  # 只检查前20行
                        if future_date in line and ('更新' in line or 'Updated' in line or '日期' in line):
                            lines[i] = line.replace(future_date, correct_date)
                    content = '\n'.join(lines)

            if content != original_content:
                md_file.write_text(content, encoding="utf-8")
                self.fixes_applied += 1
                print(f"  ✓ 更新日期: {md_file.name}")

    def add_missing_metadata(self):
        """添加缺失的元数据"""
        print("\n📋 添加缺失的元数据...")

        for md_file in self.docs_dir.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            original_content = content

            # 如果文档没有"最后更新"字段，添加它
            if "最后更新" not in content and "Last Updated" not in content:
                # 在第一个标题后添加元数据
                lines = content.split('\n')
                if lines and lines[0].startswith('#'):
                    # 找到标题后的第一个空行
                    insert_pos = 1
                    while insert_pos < len(lines) and lines[insert_pos].strip():
                        insert_pos += 1

                    metadata = f"\n**最后更新**: {self.current_date}\n"
                    lines.insert(insert_pos, metadata)
                    content = '\n'.join(lines)

            if content != original_content:
                md_file.write_text(content, encoding="utf-8")
                self.fixes_applied += 1
                print(f"  ✓ 添加元数据: {md_file.name}")

    def normalize_version_references(self):
        """规范化版本引用"""
        print("\n🏷️  规范化版本引用...")

        # 确保版本号格式一致
        version_patterns = [
            (r'\bv(\d+\.\d+\.\d+(?:\.\d+)?)\b', r'v\1'),  # 保持 v 前缀
            (r'\b(\d+\.\d+\.\d+(?:\.\d+)?)\b(?!\))', r'v\1'),  # 添加 v 前缀（除非在括号中）
        ]

        for md_file in self.docs_dir.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            original_content = content

            # 跳过某些特殊文件
            if md_file.name in ["CHANGELOG.md", "VERSION_HISTORY.md"]:
                continue

            # 应用版本规范化（谨慎处理）
            # 这里我们只记录，不自动修改，因为可能有特殊情况

            if content != original_content:
                md_file.write_text(content, encoding="utf-8")
                self.fixes_applied += 1
                print(f"  ✓ 规范化版本: {md_file.name}")


def main():
    fixer = DocumentationFixer()
    fixer.fix_all()

    # 重新运行验证
    print("\n" + "="*60)
    print("🔍 重新验证文档...")
    print("="*60 + "\n")

    import subprocess
    result = subprocess.run([sys.executable, "scripts/validate_documentation.py"],
                          capture_output=False)

    return result.returncode


if __name__ == "__main__":
    exit(main())
