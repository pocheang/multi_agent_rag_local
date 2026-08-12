"""
为文档添加 agent 分类标签并重新索引
"""
import os
import sys
from pathlib import Path

# 设置 UTF-8 编码
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import get_settings
from app.services.documents.ingest import ingest_paths


def get_agent_for_document(file_path: Path) -> str:
    """根据文件路径和名称确定 agent 类别"""
    file_str = str(file_path).lower()
    file_name = file_path.name.lower()

    # 安全相关文档
    if "security" in file_str or "cybersecurity" in file_name:
        return "cybersecurity"

    # AI/RAG 相关文档
    if any(keyword in file_name for keyword in ["artificial_intelligence", "rag", "llm", "ai_"]):
        return "artificial_intelligence"

    # PDF 相关文档
    if file_path.suffix.lower() == ".pdf":
        return "pdf_text"

    # 默认为通用
    return "general"


def main():
    """重新索引所有文档，添加 agent 分类"""
    settings = get_settings()
    data_dir = Path(settings.data_dir)

    print("=" * 60)
    print("为文档添加 Agent 分类标签")
    print("=" * 60)
    print(f"数据目录: {data_dir}")
    print()

    # 收集所有文档
    all_files = []
    for ext in [".md", ".txt", ".pdf"]:
        all_files.extend(data_dir.rglob(f"*{ext}"))

    # 过滤掉隐藏文件
    all_files = [f for f in all_files if not any(part.startswith(".") for part in f.parts)]

    if not all_files:
        print("❌ 没有找到任何文档")
        return

    print(f"找到 {len(all_files)} 个文档:")
    print()

    # 构建元数据覆盖映射
    metadata_overrides = {}
    agent_stats = {}

    for file_path in sorted(all_files):
        agent = get_agent_for_document(file_path)
        relative_path = file_path.relative_to(data_dir.parent)

        # 使用多种可能的路径格式作为 key，确保匹配
        # loaders 使用 str(path)，可能是绝对路径或相对路径
        source_keys = [
            str(file_path),  # 原始路径
            str(file_path.absolute()),  # 绝对路径
            str(file_path.resolve()),  # 解析后的路径
        ]

        for source_key in source_keys:
            metadata_overrides[source_key] = {"agent": agent}

        agent_stats[agent] = agent_stats.get(agent, 0) + 1

        print(f"📄 {relative_path}")
        print(f"   Agent: {agent}")
        print()

    print("=" * 60)
    print("分类统计:")
    print("=" * 60)
    for agent, count in sorted(agent_stats.items()):
        print(f"  {agent}: {count} 个文档")
    print()

    # 重新索引
    print("=" * 60)
    print("开始重新索引...")
    print("=" * 60)

    try:
        result = ingest_paths(
            paths=all_files,
            reset_vector_store=True,  # 清空并重新索引，确保没有旧数据
            metadata_overrides_by_source=metadata_overrides
        )

        print()
        print("✅ 索引完成!")
        print(f"  加载文档: {result.get('loaded_documents', 0)}")
        print(f"  索引块: {result.get('chunks_indexed', 0)}")
        print(f"  写入三元组: {result.get('triplets_written', 0)}")

    except Exception as e:
        print(f"❌ 索引失败: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 60)
    print("完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
