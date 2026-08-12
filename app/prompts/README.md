# Prompt modules

`app.prompts` is the public prompt package. The layout follows capability
boundaries while preserving the existing prompt constants, helper functions,
`PromptManager` keys, and public import paths.

## Directory layout

```text
app/prompts/
├── core/
│   ├── canonical_agent_prompts.py
│   ├── router_prompts.py
│   ├── intent_prompts.py
│   ├── synthesis_prompts.py
│   ├── review_prompts.py
│   └── react_prompts.py
├── retrieval/
│   ├── rag_quick_retrieval_prompts.py
│   └── self_rag_prompts.py
├── skills/
│   ├── ai_knowledge_prompts.py
│   ├── cybersecurity_skills_prompts.py
│   ├── comparison_timeline_prompts.py
│   └── pdf_web_prompts.py
├── manager.py
├── __init__.py
└── README.md
```

The following flat root modules are retained as historical compatibility
exports (they are not additional implementations):

```text
canonical_agent_prompts.py       router_prompts.py
intent_prompts.py                synthesis_prompts.py
review_prompts.py                react_prompts.py
rag_quick_retrieval_prompts.py   self_rag_prompts.py
ai_knowledge_prompts.py          cybersecurity_skills_prompts.py
comparison_timeline_prompts.py   pdf_web_prompts.py
```

## Ownership

`app.prompts.core.canonical_agent_prompts` is the only runtime canonical owner
for the router, ReAct system, answer, review, and query-decomposition prompt
templates. `core/react_prompts.py` owns the ReAct user template and imports the
canonical ReAct system prompt; it does not duplicate that system prompt.

The remaining `core` modules contain the established specialized templates.
`retrieval` contains quick-retrieval and Self-RAG templates. `skills` contains
the domain skill templates. Each prompt implementation exists in exactly one
of these capability packages.

The root prompt modules remain logic-free compatibility exports for existing
callers. They contain imports and `__all__` only; they do not define prompt
literals, helpers, registries, or managers. New production code should import
from the capability path when it needs a module-specific prompt.

## Public usage

The package-level API remains supported:

```python
from app.prompts import REACT_SYSTEM_PROMPT, get_prompt_manager
```

The canonical runtime module and historical root path are both supported:

```python
from app.prompts.core.canonical_agent_prompts import ANSWER_PROMPT
from app.prompts.canonical_agent_prompts import REACT_SYSTEM_PROMPT
```

Use the manager through its established entry point:

```python
from app.prompts.manager import PromptManager

manager = PromptManager()
system_prompt, user_template = manager.get_router_prompts()
```

`app.prompts.manager.get_prompt_manager()` continues to return the existing
singleton. Do not change prompt keys, return values, formatting behavior, or
the prompt text when adding or relocating a prompt.
