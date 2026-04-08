from app.ingestion.graph_extractor import extract_triplets


def test_extract_triplets_returns_list():
    text = "LangGraph 使用 Neo4j 和 Chroma 构建多智能体 RAG 系统。"
    triplets = extract_triplets(text)
    assert isinstance(triplets, list)
