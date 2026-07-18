#!/usr/bin/env python3
"""
Chunker Enhanced 文件修复工具
诊断并修复 chunker_enhanced.py 的语法错误
"""

import sys
import os

def diagnose_file(filepath):
    """诊断文件问题"""
    print("=" * 60)
    print("诊断 chunker_enhanced.py")
    print("=" * 60)

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')

    # 统计三引号
    triple_count = content.count('"""')
    print(f"\n1. 三引号总数: {triple_count}")
    print(f"   是否配对: {'✅ 是' if triple_count % 2 == 0 else '❌ 否 (奇数)'}")

    # 追踪文档字符串
    print("\n2. 文档字符串追踪:")
    in_docstring = False
    unclosed = []

    for i, line in enumerate(lines, 1):
        count = line.count('"""')
        if count > 0:
            for _ in range(count):
                if not in_docstring:
                    in_docstring = True
                    unclosed.append(i)
                else:
                    in_docstring = False
                    if unclosed:
                        unclosed.pop()

    if unclosed:
        print(f"   ❌ 未闭合的文档字符串起始行: {unclosed}")
        for line_num in unclosed:
            print(f"      第 {line_num} 行: {lines[line_num-1][:80]}")
    else:
        print(f"   ✅ 所有文档字符串都已闭合")

    # 检查文件结尾
    print("\n3. 文件结尾检查:")
    print(f"   总行数: {len(lines)}")
    print(f"   最后一行: {repr(lines[-1][:80] if lines else '')}")
    print(f"   倒数第2行: {repr(lines[-2][:80] if len(lines) > 1 else '')}")
    print(f"   倒数第3行: {repr(lines[-3][:80] if len(lines) > 2 else '')}")

    return triple_count % 2 == 0, unclosed

def fix_file(filepath):
    """修复文件"""
    print("\n" + "=" * 60)
    print("修复策略")
    print("=" * 60)

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 检查并修复
    fixed = False

    # 策略1: 确保文件以换行结束
    if lines and not lines[-1].endswith('\n'):
        print("\n✓ 策略1: 添加文件结尾换行符")
        lines[-1] += '\n'
        fixed = True

    # 策略2: 移除多余的空行
    while len(lines) > 1 and lines[-1].strip() == '' and lines[-2].strip() == '':
        print(f"✓ 策略2: 移除多余空行 (行 {len(lines)})")
        lines.pop()
        fixed = True

    if fixed:
        # 写回文件
        backup_path = filepath + '.backup'
        print(f"\n✓ 创建备份: {backup_path}")
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        print(f"✓ 写入修复后的文件")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        return True
    else:
        print("\n✗ 未发现明显问题，无需修复")
        return False

def verify_syntax(filepath):
    """验证Python语法"""
    print("\n" + "=" * 60)
    print("验证Python语法")
    print("=" * 60)

    import py_compile
    try:
        py_compile.compile(filepath, doraise=True)
        print("✅ 语法检查通过！")
        return True
    except SyntaxError as e:
        print(f"❌ 语法错误:")
        print(f"   文件: {e.filename}")
        print(f"   行号: {e.lineno}")
        print(f"   错误: {e.msg}")
        if e.text:
            print(f"   代码: {e.text.strip()}")
        return False

def main():
    filepath = 'app/ingestion/chunker_enhanced.py'

    if not os.path.exists(filepath):
        print(f"❌ 文件不存在: {filepath}")
        return 1

    # 步骤1: 诊断
    is_paired, unclosed = diagnose_file(filepath)

    # 步骤2: 尝试修复
    if not is_paired or unclosed:
        print("\n⚠️ 发现问题，尝试修复...")
        fixed = fix_file(filepath)

        if fixed:
            # 重新诊断
            print("\n" + "=" * 60)
            print("重新诊断")
            print("=" * 60)
            is_paired_after, unclosed_after = diagnose_file(filepath)

    # 步骤3: 验证语法
    if verify_syntax(filepath):
        print("\n" + "=" * 60)
        print("✅ 修复成功！")
        print("=" * 60)
        return 0
    else:
        print("\n" + "=" * 60)
        print("❌ 语法错误仍然存在")
        print("=" * 60)
        print("\n建议: 手动检查文件或使用备份文件")
        return 1

if __name__ == '__main__':
    sys.exit(main())
