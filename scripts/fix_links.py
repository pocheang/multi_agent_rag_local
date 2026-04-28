#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量修复文档链接"""

import re
from pathlib import Path

def fix_version_history():
    """修复 VERSION_HISTORY.md 中的链接"""
    file_path = Path('docs/VERSION_HISTORY.md')
    content = file_path.read_text(encoding='utf-8')

    # 修复模式
    fixes = [
        ('CHANGELOG_2026-04-27.md', '../CHANGELOG.md'),
        ('FINAL_FIXES_SUMMARY_2026-04-27.md', 'archive/FIXES_SUMMARY.md'),
        ('DEEP_CODE_REVIEW_2026-04-27.md', 'archive/DEEP_CODE_REVIEW_2026-04-27.md'),
        ('LOGIC_FIXES_2026-04-27.md', 'archive/FIXES_SUMMARY.md'),
        ('FIXES_ROUND2_2026-04-27.md', 'archive/FIXES_SUMMARY.md'),
        ('FIXES_ROUND3_2026-04-27.md', 'archive/FIXES_SUMMARY.md'),
        ('FIXES_ROUND4_2026-04-27.md', 'archive/FIXES_SUMMARY.md'),
        ('](FIXES_INDEX.md)', '](archive/FIXES_INDEX.md)'),
        ('](production_readiness_checklist.md)', '](archive/production_readiness_checklist.md)'),
    ]

    for old, new in fixes:
        content = content.replace(old, new)

    # 修复 CHANGELOG 锚点链接
    content = re.sub(r'CHANGELOG\.md#\d+---\d{4}-\d{2}-\d{2}', '../CHANGELOG.md', content)

    file_path.write_text(content, encoding='utf-8')
    return True

def fix_documentation_org_summary():
    """修复 DOCUMENTATION_ORGANIZATION_SUMMARY.md 中的链接"""
    file_path = Path('docs/DOCUMENTATION_ORGANIZATION_SUMMARY.md')
    if not file_path.exists():
        return False

    content = file_path.read_text(encoding='utf-8')

    # 修复 CLAUDE.md 链接
    content = content.replace('](CLAUDE.md)', '](../CLAUDE.md)')

    file_path.write_text(content, encoding='utf-8')
    return True

if __name__ == '__main__':
    print('Fixing documentation links...')

    if fix_version_history():
        print('Fixed VERSION_HISTORY.md')

    if fix_documentation_org_summary():
        print('Fixed DOCUMENTATION_ORGANIZATION_SUMMARY.md')

    print('Done!')
