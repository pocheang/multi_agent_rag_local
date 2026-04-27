#!/usr/bin/env python3
"""
验证 v0.3.0 重构后的导入完整性
"""
import ast
import sys
from pathlib import Path
from collections import defaultdict

def extract_imports(file_path):
    """提取文件中的所有导入和使用的名称"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except SyntaxError as e:
        return None, f"Syntax error: {e}"

    imported_names = set()
    used_names = set()

    for node in ast.walk(tree):
        # 收集导入的名称
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.asname if alias.asname else alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != '*':
                    imported_names.add(alias.asname if alias.asname else alias.name)

        # 收集使用的名称（函数调用）
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                used_names.add(node.func.id)

    return imported_names, used_names

def check_file(file_path):
    """检查单个文件的导入完整性"""
    imported, used = extract_imports(file_path)

    if isinstance(imported, type(None)):
        return False, used  # used contains error message

    # 内置函数和常见名称
    builtins = {
        'print', 'len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple',
        'range', 'enumerate', 'zip', 'map', 'filter', 'sorted', 'sum', 'max', 'min',
        'any', 'all', 'isinstance', 'hasattr', 'getattr', 'setattr', 'type',
        'open', 'round', 'abs', 'pow', 'divmod', 'hash', 'id', 'hex', 'oct', 'bin',
    }

    # 检查未导入但使用的名称
    undefined = used - imported - builtins

    # 过滤掉可能是方法调用的名称（这个检查不完美，但能捕获大部分问题）
    critical_undefined = {
        name for name in undefined
        if name in [
            'emit_alert', 'normalize_retrieval_profile', 'classify_agent_class',
            'choose_shadow', 'append_shadow_run', 'text_similarity',
            'resolve_profile_for_request', 'run_query'
        ]
    }

    return len(critical_undefined) == 0, critical_undefined

def main():
    """主函数"""
    project_root = Path(__file__).parent
    api_dir = project_root / "app" / "api"

    print("=" * 80)
    print("v0.3.0 重构导入完整性验证")
    print("=" * 80)
    print()

    files_to_check = [
        api_dir / "dependencies.py",
        api_dir / "routes" / "query.py",
        api_dir / "routes" / "admin_ops.py",
        api_dir / "routes" / "admin_settings.py",
        api_dir / "routes" / "sessions.py",
        api_dir / "routes" / "auth.py",
        api_dir / "routes" / "documents.py",
        api_dir / "routes" / "health.py",
        api_dir / "routes" / "prompts.py",
        api_dir / "routes" / "admin_users.py",
    ]

    all_passed = True
    issues = defaultdict(list)

    for file_path in files_to_check:
        if not file_path.exists():
            print(f"❌ {file_path.relative_to(project_root)}: 文件不存在")
            all_passed = False
            continue

        passed, undefined = check_file(file_path)
        rel_path = file_path.relative_to(project_root)

        if passed:
            print(f"✅ {rel_path}")
        else:
            print(f"❌ {rel_path}")
            if isinstance(undefined, str):
                print(f"   错误: {undefined}")
                issues[str(rel_path)].append(undefined)
            else:
                for name in sorted(undefined):
                    print(f"   缺失导入: {name}")
                    issues[str(rel_path)].append(name)
            all_passed = False

    print()
    print("=" * 80)

    if all_passed:
        print("✅ 所有文件导入检查通过！")
        print()
        print("下一步:")
        print("1. 运行测试: pytest -q")
        print("2. 启动服务: uvicorn app.api.main:app --reload")
        return 0
    else:
        print("❌ 发现导入问题，需要修复")
        print()
        print("问题汇总:")
        for file, problems in issues.items():
            print(f"\n{file}:")
            for problem in problems:
                print(f"  - {problem}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
