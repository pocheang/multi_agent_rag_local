import uuid
from pathlib import Path

from app.services.prompt_store import PromptStore


def _mk(prefix: str) -> Path:
    path = Path("tests/.tmp") / f"{prefix}-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_prompt_store_crud():
    root = _mk("prompt-store")
    store = PromptStore(db_path=root / "app.db")
    user_id = "u1"

    created = store.create_prompt(user_id=user_id, title="分析模板", content="请按攻击链分析")
    assert created["prompt_id"]
    assert created["agent_class"] == "general"

    listed = store.list_prompts(user_id=user_id)
    assert len(listed) == 1
    assert listed[0]["title"] == "分析模板"
    assert listed[0]["agent_class"] == "general"

    updated = store.update_prompt(
        user_id=user_id,
        prompt_id=created["prompt_id"],
        title="新标题",
        content="新内容",
        agent_class="cybersecurity",
    )
    assert updated is not None
    assert updated["title"] == "新标题"
    assert updated["agent_class"] == "cybersecurity"

    ok = store.delete_prompt(user_id=user_id, prompt_id=created["prompt_id"])
    assert ok is True
    assert store.list_prompts(user_id=user_id) == []
