from app.tools.web_search import search_web


def run_web_research(question: str) -> dict:
    results = search_web(question, max_results=5)
    lines = []
    citations = []
    for item in results:
        title = item.get("title", "")
        href = item.get("href", "")
        body = item.get("body", "")
        lines.append(f"[WEB] {title}\nURL: {href}\n{body}")
        citations.append({"source": href or title, "content": body, "metadata": {"title": title}})
    return {"context": "\n\n".join(lines), "citations": citations, "used": bool(results)}
