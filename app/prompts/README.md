# Prompt modules

`app.prompts` holds the prompt constants shared across agents.

## Directory layout

```text
app/prompts/
├── __init__.py                      # re-exports the shared prompt symbols
└── core/
    └── canonical_agent_prompts.py   # ANSWER/REVIEW prompts, build_router_prompt,
                                     # QUERY_DECOMPOSITION_PROMPT
```

## Where the other prompts live

Prompts owned by a single agent live next to that agent, not here:

| Prompt family | Location |
|---|---|
| Answer templates, chain-of-thought | `app/agents/synthesizer/templates.py` |
| Router few-shot examples | `app/agents/router/examples.py` |
| Planner decomposition | `app/agents/planner/prompts.py` |
| Knowledge strategy | `app/agents/knowledge/prompts.py` |
| Clarification questions | `app/agents/clarification/rules.py` |

## History

Until 2026-08-29 this package also carried a 468-line `PromptManager`, four
"skills" prompt catalogues, and separate router / intent / review / synthesis /
self-RAG modules — roughly 3,400 lines across 25 modules. A full-backend audit
found that exactly two names were ever imported from outside the package
(`build_router_prompt` and `QUERY_DECOMPOSITION_PROMPT`), both defined in
`core/canonical_agent_prompts.py`. The unused modules were deleted rather than
kept as a library nobody called.
