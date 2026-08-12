#!/usr/bin/env python3
"""
文档工具包 (Document Toolkit)
===============================

一站式文档管理工具，集成切片、上传、索引功能

功能：
1. 上传文档并自动切片
2. 查看切片统计和分类
3. 重新索引文档
4. 查看文档索引状态
5. 批量管理文档

使用示例：
---------
# 上传单个文档
python scripts/document_toolkit.py upload path/to/doc.pdf

# 上传并查看切片详情
python scripts/document_toolkit.py upload path/to/doc.pdf --show-chunks

# 查看已索引文档
python scripts/document_toolkit.py list

# 查看切片统计
python scripts/document_toolkit.py stats

# 重新索引文档（使用增强切片）
python scripts/document_toolkit.py reindex doc.pdf --enhanced

# 批量上传目录
python scripts/document_toolkit.py upload-dir ./documents --recursive
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import basic chunker first
from app.ingestion.chunker import split_documents as split_documents_basic

# Try to import enhanced chunker, fallback to basic if it fails
try:
    from app.ingestion.chunker_enhanced import split_documents as split_documents_enhanced
    ENHANCED_AVAILABLE = True
except (ImportError, SyntaxError) as e:
    print(f"Warning: Enhanced chunker not available ({e}), using basic chunker")
    split_documents_enhanced = split_documents_basic
    ENHANCED_AVAILABLE = False
from app.ingestion.loaders import load_documents
from app.services.documents.index_manager import list_indexed_files, rebuild_file_index, delete_file_index
from app.services.documents.registry import list_document_records, create_document_record

# Import vector store with fallback
try:
    from app.retrievers.stores.vector import get_vector_store
    VECTOR_STORE_AVAILABLE = True
except ImportError:
    get_vector_store = None
    VECTOR_STORE_AVAILABLE = False


class DocumentToolkit:
    """文档管理工具类"""

    def __init__(self):
        if VECTOR_STORE_AVAILABLE:
            self.vector_store = get_vector_store()
        else:
            self.vector_store = None

    def upload_and_index(
        self,
        file_path: str,
        use_enhanced: bool = True,
        show_chunks: bool = False,
        owner_user_id: str = "admin",
        visibility: str = "private",
        agent_class: str = "general"
    ) -> dict[str, Any]:
        """
        上传文档并索引

        Args:
            file_path: 文档路径
            use_enhanced: 使用增强切片器
            show_chunks: 显示切片详情
            owner_user_id: 所有者用户ID
            visibility: 可见性 (private/public)
            agent_class: Agent类别

        Returns:
            上传结果统计
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        print(f"📄 正在加载文档: {path.name}")
        documents = load_documents(str(path))
        print(f"✅ 加载完成: {len(documents)} 个文档片段")

        # 选择切片器
        if use_enhanced:
            print("🔧 使用增强切片器 (14种类型分类)")
            chunks, parents = split_documents_enhanced(documents)
        else:
            print("🔧 使用基础切片器")
            chunks, parents = split_documents_basic(documents)

        print(f"✂️  切片完成: {len(chunks)} 个chunks")

        # 分析切片类型分布
        chunk_types = {}
        total_length = 0
        for chunk in chunks:
            chunk_type = chunk.metadata.get('chunk_type', 'unknown')
            chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1
            total_length += len(chunk.page_content)

        # 索引到向量存储
        if self.vector_store:
            print("📊 正在索引到向量存储...")

            # 准备元数据
            for chunk in chunks:
                chunk.metadata.update({
                    'source': str(path.absolute()),
                    'filename': path.name,
                    'owner_user_id': owner_user_id,
                    'visibility': visibility,
                    'agent_class': agent_class,
                })

            # 添加到向量存储
            self.vector_store.add_documents(chunks)
        else:
            print("⚠️ 向量存储不可用，跳过索引")

        # 创建文档记录
        try:
            create_document_record(
                filename=path.name,
                source=str(path.absolute()),
                owner_user_id=owner_user_id,
                visibility=visibility,
                agent_class=agent_class,
                chunks_indexed=len(chunks),
                status="ready",
            )
        except Exception as e:
            print(f"⚠️  创建文档记录失败: {e}")

        # 显示统计
        print("\n" + "="*60)
        print("📊 上传统计")
        print("="*60)
        print(f"文件名: {path.name}")
        print(f"总chunks: {len(chunks)}")
        print(f"总字符数: {total_length:,}")
        print(f"平均chunk长度: {total_length // len(chunks) if chunks else 0}")
        print(f"\n🏷️  Chunk类型分布:")
        for chunk_type, count in sorted(chunk_types.items(), key=lambda x: -x[1]):
            percentage = (count / len(chunks) * 100) if chunks else 0
            print(f"  {chunk_type:15s}: {count:4d} ({percentage:5.1f}%)")

        # 显示chunk详情
        if show_chunks and chunks:
            print(f"\n📋 前5个Chunks预览:")
            for i, chunk in enumerate(chunks[:5], 1):
                chunk_type = chunk.metadata.get('chunk_type', 'unknown')
                keywords = chunk.metadata.get('keywords', [])
                importance = chunk.metadata.get('importance_score', 0.0)
                preview = chunk.page_content[:100].replace('\n', ' ')

                print(f"\n  [{i}] 类型: {chunk_type}")
                print(f"      重要性: {importance:.2f}")
                print(f"      关键词: {', '.join(keywords[:5])}")
                print(f"      预览: {preview}...")

        return {
            'filename': path.name,
            'chunks': len(chunks),
            'chunk_types': chunk_types,
            'total_chars': total_length,
            'avg_chunk_length': total_length // len(chunks) if chunks else 0,
        }

    def list_documents(self, show_details: bool = False) -> list[dict[str, Any]]:
        """列出所有已索引文档"""
        docs = list(list_indexed_files())

        print(f"\n📚 已索引文档: {len(docs)} 个")
        print("="*80)

        for i, doc in enumerate(docs, 1):
            filename = doc.get('filename', 'unknown')
            chunks = doc.get('chunks', 0)
            agent_class = doc.get('agent_class', 'general')
            visibility = doc.get('visibility', 'private')

            print(f"{i:3d}. {filename:40s} | {chunks:4d} chunks | {agent_class:10s} | {visibility}")

            if show_details:
                source = doc.get('source', '')
                owner = doc.get('owner_user_id', '')
                status = doc.get('indexing_status', 'unknown')
                print(f"     源: {source}")
                print(f"     所有者: {owner} | 状态: {status}")

        return docs

    def show_chunk_stats(self) -> dict[str, Any]:
        """显示全局切片统计"""
        print("\n📊 全局Chunk统计")
        print("="*60)

        # 从向量存储获取所有文档
        if not self.vector_store:
            print("⚠️  向量存储未初始化")
            return {}

        try:
            # 使用 _collection 属性访问内部集合
            collection = self.vector_store._collection
            if not collection:
                print("❌ 向量存储未初始化")
                return {}

            # 获取所有文档的元数据
            results = collection.get(include=['metadatas'])
            metadatas = results.get('metadatas', [])

            if not metadatas:
                print("⚠️  没有找到任何chunks")
                return {}

            # 统计chunk类型
            chunk_types = {}
            importance_scores = []
            sources = set()

            for meta in metadatas:
                chunk_type = meta.get('chunk_type', 'unknown')
                chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1

                importance = meta.get('importance_score')
                if importance is not None:
                    importance_scores.append(float(importance))

                source = meta.get('source')
                if source:
                    sources.add(source)

            total_chunks = len(metadatas)

            print(f"总Chunks: {total_chunks:,}")
            print(f"文档数量: {len(sources)}")

            if importance_scores:
                avg_importance = sum(importance_scores) / len(importance_scores)
                print(f"平均重要性得分: {avg_importance:.3f}")

            print(f"\n🏷️  Chunk类型分布:")
            for chunk_type, count in sorted(chunk_types.items(), key=lambda x: -x[1]):
                percentage = (count / total_chunks * 100)
                bar = '█' * int(percentage / 2)
                print(f"  {chunk_type:15s}: {count:6,d} ({percentage:5.1f}%) {bar}")

            return {
                'total_chunks': total_chunks,
                'document_count': len(sources),
                'chunk_types': chunk_types,
                'avg_importance': sum(importance_scores) / len(importance_scores) if importance_scores else 0,
            }

        except Exception as e:
            print(f"❌ 统计失败: {e}")
            return {}

    def search_by_type(
        self,
        query: str,
        chunk_type: str | list[str] | None = None,
        k: int = 5
    ) -> list[Any]:
        """
        按类型搜索chunks

        Args:
            query: 查询文本
            chunk_type: chunk类型过滤
            k: 返回结果数量
        """
        print(f"\n🔍 搜索: '{query}'")
        if chunk_type:
            print(f"   类型过滤: {chunk_type}")

        # 构建过滤条件
        filter_dict = {}
        if chunk_type:
            if isinstance(chunk_type, list):
                filter_dict['chunk_type'] = {'$in': chunk_type}
            else:
                filter_dict['chunk_type'] = chunk_type

        results = self.vector_store.similarity_search(
            query=query,
            k=k,
            filter=filter_dict if filter_dict else None
        )

        print(f"\n✅ 找到 {len(results)} 个结果:")
        print("="*80)

        for i, doc in enumerate(results, 1):
            chunk_type = doc.metadata.get('chunk_type', 'unknown')
            source = doc.metadata.get('source', 'unknown')
            filename = Path(source).name if source != 'unknown' else 'unknown'
            importance = doc.metadata.get('importance_score', 0.0)
            keywords = doc.metadata.get('keywords', [])

            preview = doc.page_content[:150].replace('\n', ' ')

            print(f"\n[{i}] {filename} | 类型: {chunk_type} | 重要性: {importance:.2f}")
            if keywords:
                print(f"    关键词: {', '.join(keywords[:5])}")
            print(f"    预览: {preview}...")

        return results

    def reindex_document(
        self,
        filename: str,
        use_enhanced: bool = True,
        source: str | None = None
    ):
        """重新索引文档"""
        # 查找文档源路径
        if not source:
            for doc in list_indexed_files():
                if doc.get('filename') == filename:
                    source = doc.get('source')
                    break

        if not source:
            raise ValueError(f"找不到文档: {filename}")

        print(f"🔄 重新索引: {filename}")

        # 删除旧索引
        print("  删除旧索引...")
        delete_file_index(filename, remove_physical_file=False, source=source)

        # 重新上传
        print("  重新切片和索引...")
        return self.upload_and_index(source, use_enhanced=use_enhanced)


def main():
    parser = argparse.ArgumentParser(
        description='文档工具包 - 一站式文档管理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest='command', help='命令')

    # upload命令
    upload_parser = subparsers.add_parser('upload', help='上传文档')
    upload_parser.add_argument('file', help='文档路径')
    upload_parser.add_argument('--basic', action='store_true', help='使用基础切片器（默认使用增强版）')
    upload_parser.add_argument('--show-chunks', action='store_true', help='显示chunk详情')
    upload_parser.add_argument('--owner', default='admin', help='所有者用户ID')
    upload_parser.add_argument('--visibility', default='private', choices=['private', 'public'], help='可见性')
    upload_parser.add_argument('--agent-class', default='general', help='Agent类别')

    # list命令
    list_parser = subparsers.add_parser('list', help='列出已索引文档')
    list_parser.add_argument('--details', action='store_true', help='显示详细信息')

    # stats命令
    stats_parser = subparsers.add_parser('stats', help='显示切片统计')

    # search命令
    search_parser = subparsers.add_parser('search', help='搜索chunks')
    search_parser.add_argument('query', help='搜索查询')
    search_parser.add_argument('--type', help='chunk类型过滤 (逗号分隔多个类型)')
    search_parser.add_argument('-k', type=int, default=5, help='返回结果数量')

    # reindex命令
    reindex_parser = subparsers.add_parser('reindex', help='重新索引文档')
    reindex_parser.add_argument('filename', help='文档文件名')
    reindex_parser.add_argument('--basic', action='store_true', help='使用基础切片器')
    reindex_parser.add_argument('--source', help='文档源路径（可选）')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    toolkit = DocumentToolkit()

    try:
        if args.command == 'upload':
            toolkit.upload_and_index(
                file_path=args.file,
                use_enhanced=not args.basic,
                show_chunks=args.show_chunks,
                owner_user_id=args.owner,
                visibility=args.visibility,
                agent_class=args.agent_class,
            )

        elif args.command == 'list':
            toolkit.list_documents(show_details=args.details)

        elif args.command == 'stats':
            toolkit.show_chunk_stats()

        elif args.command == 'search':
            chunk_types = None
            if args.type:
                chunk_types = [t.strip() for t in args.type.split(',')]
                if len(chunk_types) == 1:
                    chunk_types = chunk_types[0]

            toolkit.search_by_type(
                query=args.query,
                chunk_type=chunk_types,
                k=args.k
            )

        elif args.command == 'reindex':
            toolkit.reindex_document(
                filename=args.filename,
                use_enhanced=not args.basic,
                source=args.source
            )

    except Exception as e:
        print(f"\n❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
