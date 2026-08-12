# MCP integration

QueryMind exposes its public RAG capabilities as a local stdio [Model Context
Protocol (MCP)](https://modelcontextprotocol.io/) server. The server is an
adapter over `RAGPipeline`; it does not call implementation agents directly.
This keeps routing, retrieval, citation generation, validation, and fallback
policy identical to the existing API profiles.

## Install and run

Use the required Conda environment and install the project dependencies:

```powershell
conda activate rag-local
pip install -e .
python -m app.mcp.server
```

The process uses standard input/output for MCP JSON-RPC. Do not write banners,
debug output, or application logs to standard output.

For an MCP desktop client, configure the command to run `python -m
app.mcp.server` with its interpreter set to the `rag-local` Conda environment.

## Tools

- `list_rag_agents`: lists the five stable, pipeline-facing capabilities.
- `query_standard_rag`: standard local RAG profile; can opt into reasoning or
  web fallback.
- `query_strict_quality_rag`: quality-first profile with routing, retrieval,
  and answer validation.
- `query_advanced_rag`: advanced profile; query decomposition and Self-RAG are
  explicit opt-ins.

All query tools return a normalized answer, route, citations, quality report,
and any degradation events. `allowed_sources` limits a query to named sources;
when it is omitted, the server uses the profile's existing unrestricted-local
behavior.

## Security

stdio MCP has no HTTP authentication layer: any process that can launch this
server can query the knowledge base available to that operating-system user.
Run it only for trusted local MCP clients. For multi-user or remote access,
continue using the authenticated FastAPI endpoints rather than exposing this
stdio process over the network.
