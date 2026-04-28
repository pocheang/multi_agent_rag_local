#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档验证和更新脚本
验证文档的完整性、一致性和准确性
"""

import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import json

# 设置输出编码
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


class DocumentationValidator:
    def __init__(self, docs_dir: Path = Path("docs")):
        self.docs_dir = docs_dir
        self.issues: List[Dict] = []
        self.stats: Dict = {
            "total_files": 0,
            "checked_files": 0,
            "broken_links": 0,
            "outdated_dates": 0,
            "missing_metadata": 0,
        }

    def validate_all(self):
        """运行所有验证检查"""
        print("🔍 开始文档验证...\n")

        self.check_file_structure()
        self.validate_metadata()
        self.check_internal_links()
        self.check_date_consistency()
        self.check_version_references()

        self.print_report()

    def check_file_structure(self):
        """检查文档目录结构"""
        print("📁 检查文档结构...")

        required_dirs = ["archive", "security", "design", "development", "operations"]
        for dir_name in required_dirs:
            dir_path = self.docs_dir / dir_name
            if not dir_path.exists():
                self.issues.append({
                    "type": "structure",
                    "severity": "warning",
                    "message": f"缺少目录: {dir_name}"
                })

        # 统计文档数量
        md_files = list(self.docs_dir.rglob("*.md"))
        self.stats["total_files"] = len(md_files)
        print(f"  ✓ 找到 {len(md_files)} 个文档文件")

    def validate_metadata(self):
        """验证文档元数据"""
        print("\n📋 验证文档元数据...")

        for md_file in self.docs_dir.rglob("*.md"):
            self.stats["checked_files"] += 1
            content = md_file.read_text(encoding="utf-8")

            # 检查是否有标题
            if not content.startswith("#"):
                self.issues.append({
                    "type": "metadata",
                    "severity": "warning",
                    "file": str(md_file),
                    "message": "文档缺少标题"
                })

            # 检查是否有更新日期
            if "最后更新" not in content and "Last Updated" not in content:
                self.stats["missing_metadata"] += 1
                self.issues.append({
                    "type": "metadata",
                    "severity": "info",
                    "file": str(md_file),
                    "message": "文档缺少更新日期"
                })

        print(f"  ✓ 检查了 {self.stats['checked_files']} 个文件")

    def check_internal_links(self):
        """检查内部链接有效性"""
        print("\n🔗 检查内部链接...")

        for md_file in self.docs_dir.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")

            # 查找 Markdown 链接
            links = re.findall(r'\[([^\]]+)\]\(([^\)]+)\)', content)

            for link_text, link_url in links:
                # 跳过外部链接
                if link_url.startswith(("http://", "https://", "#")):
                    continue

                # 解析相对路径
                if link_url.startswith("../"):
                    target = (md_file.parent / link_url).resolve()
                elif link_url.startswith("./"):
                    target = (md_file.parent / link_url[2:]).resolve()
                else:
                    target = (md_file.parent / link_url).resolve()

                # 检查文件是否存在
                if not target.exists():
                    self.stats["broken_links"] += 1
                    self.issues.append({
                        "type": "link",
                        "severity": "error",
                        "file": str(md_file),
                        "message": f"断开的链接: {link_url} -> {target}"
                    })

        print(f"  ✓ 发现 {self.stats['broken_links']} 个断开的链接")

    def check_date_consistency(self):
        """检查日期一致性"""
        print("\n📅 检查日期一致性...")

        today = datetime.now().strftime("%Y-%m-%d")

        for md_file in self.docs_dir.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")

            # 查找日期模式
            dates = re.findall(r'202[0-9]-[0-1][0-9]-[0-3][0-9]', content)

            # 检查是否有未来日期
            for date_str in dates:
                if date_str > today:
                    self.stats["outdated_dates"] += 1
                    self.issues.append({
                        "type": "date",
                        "severity": "warning",
                        "file": str(md_file),
                        "message": f"发现未来日期: {date_str}"
                    })

        print(f"  ✓ 检查完成")

    def check_version_references(self):
        """检查版本引用一致性"""
        print("\n🏷️  检查版本引用...")

        version_pattern = r'v?0\.\d+\.\d+(?:\.\d+)?'
        version_counts = {}

        for md_file in self.docs_dir.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            versions = re.findall(version_pattern, content)

            for version in versions:
                version_counts[version] = version_counts.get(version, 0) + 1

        print(f"  ✓ 找到 {len(version_counts)} 个不同的版本引用")

        # 显示最常见的版本
        top_versions = sorted(version_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        for version, count in top_versions:
            print(f"    - {version}: {count} 次引用")

    def print_report(self):
        """打印验证报告"""
        print("\n" + "="*60)
        print("📊 文档验证报告")
        print("="*60)

        print(f"\n统计信息:")
        print(f"  总文件数: {self.stats['total_files']}")
        print(f"  已检查: {self.stats['checked_files']}")
        print(f"  断开的链接: {self.stats['broken_links']}")
        print(f"  日期问题: {self.stats['outdated_dates']}")
        print(f"  缺少元数据: {self.stats['missing_metadata']}")

        # 按严重程度分组问题
        errors = [i for i in self.issues if i["severity"] == "error"]
        warnings = [i for i in self.issues if i["severity"] == "warning"]
        infos = [i for i in self.issues if i["severity"] == "info"]

        print(f"\n问题汇总:")
        print(f"  🔴 错误: {len(errors)}")
        print(f"  🟡 警告: {len(warnings)}")
        print(f"  ℹ️  信息: {len(infos)}")

        # 显示错误详情
        if errors:
            print(f"\n🔴 错误详情:")
            for issue in errors[:10]:  # 只显示前10个
                print(f"  - {issue['file']}")
                print(f"    {issue['message']}")

        # 显示警告详情
        if warnings and len(warnings) <= 10:
            print(f"\n🟡 警告详情:")
            for issue in warnings:
                print(f"  - {issue.get('file', 'N/A')}")
                print(f"    {issue['message']}")

        # 保存完整报告
        report_file = Path("docs/VALIDATION_REPORT.json")
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "stats": self.stats,
                "issues": self.issues
            }, f, indent=2, ensure_ascii=False)

        print(f"\n✅ 完整报告已保存到: {report_file}")

        # 返回状态码
        if errors:
            print("\n❌ 验证失败: 发现错误")
            return 1
        elif warnings:
            print("\n⚠️  验证通过: 但有警告")
            return 0
        else:
            print("\n✅ 验证通过: 无问题")
            return 0


def main():
    validator = DocumentationValidator()
    exit_code = validator.validate_all()
    return exit_code


if __name__ == "__main__":
    exit(main())
