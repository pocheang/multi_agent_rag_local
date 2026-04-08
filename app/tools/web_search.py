from ddgs import DDGS


def search_web(query: str, max_results: int = 5) -> list[dict]:
    results: list[dict] = []
    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=max_results, region="wt-wt", safesearch="moderate"):
            results.append(
                {
                    "title": item.get("title", ""),
                    "href": item.get("href", ""),
                    "body": item.get("body", ""),
                }
            )
    return results
