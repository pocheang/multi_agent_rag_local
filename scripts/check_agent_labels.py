"""
检查文档的 agent 分类标签
"""
import os
import sys
from pathlib import Path
from collections import defaultdict

# 设置 UTF-8 编码
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.retrievers.stores.corpus import read_corpus_records


def main():
    """检查 corpus 中的 agent 分类"""
    print("=" * 60)
    print("检查文档 Agent 分类")
    print("=" * 60)
    print()

    records = read_corpus_records()
    print(f"总记录数: {len(records)}")
    print()

    # 按 agent 分组
    by_agent = defaultdict(list)
    by_source = defaultdict(set)

    for record in records:
        metadata = record.get("metadata", {})
        agent = metadata.get("agent", "未分类")
        source = metadata.get("source", "未知来源")

        by_agent[agent].append(record)
        by_source[agent].add(source)

    # 显示统计
    print("=" * 60)
    print("按 Agent 分类统计:")
    print("=" * 60)
    for agent in sorted(by_agent.keys()):
        chunks = len(by_agent[agent])
        sources = len(by_source[agent])
        print(f"\n{agent}:")
        print(f"  文档数: {sources}")
        print(f"  块数: {chunks}")
        print(f"  文档列表:")
        for source in sorted(by_source[agent]):
            # 只显示文件名
            filename = Path(source).name
            source_chunks = [r for r in by_agent[agent] if r.get("metadata", {}).get("source") == source]
            print(f"    - {filename} ({len(source_chunks)} 块)")

    print()
    print("=" * 60)
    print("完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
