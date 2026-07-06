import json
import sys

def validate_json_file(filepath):
    """验证并修复JSON文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # 尝试解析JSON
        data = json.loads(content)
        print(f"✅ {filepath} is valid JSON")
        return True

    except json.JSONDecodeError as e:
        print(f"❌ JSON Error in {filepath}:")
        print(f"   Line {e.lineno}, Column {e.colno}")
        print(f"   Message: {e.msg}")
        print(f"   Position: {e.pos}")

        # 显示错误上下文
        lines = content.split('\n')
        start = max(0, e.lineno - 3)
        end = min(len(lines), e.lineno + 2)

        print(f"\n   Context:")
        for i in range(start, end):
            marker = ">>> " if i == e.lineno - 1 else "    "
            print(f"   {marker}{i+1:4d} | {lines[i]}")

        return False

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        filepath = "frontend/src/i18n/locales/zh.json"

    validate_json_file(filepath)
