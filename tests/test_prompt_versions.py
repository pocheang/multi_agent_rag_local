from app.services.prompt_store import PromptStore
from pathlib import Path
import uuid


def test_prompt_versions_and_rollback():
    base = Path("data") / "test_tmp" / f"prompt_versions_{uuid.uuid4().hex}"
    base.mkdir(parents=True, exist_ok=True)
    store = PromptStore(db_path=base / "app.db")
    created = store.create_prompt(user_id="u1", title="t1", content="c1", agent_class="general")
    prompt_id = str(created["prompt_id"])
    store.update_prompt(user_id="u1", prompt_id=prompt_id, title="t2", content="c2", agent_class="policy")
    versions = store.list_versions(user_id="u1", prompt_id=prompt_id, limit=10)
    assert len(versions) >= 2
    old_version = versions[-1]
    approved = store.approve_version(user_id="u1", prompt_id=prompt_id, version_id=str(old_version["version_id"]), approved_by="admin")
    assert approved is not None
    assert approved["status"] == "approved"
    rolled = store.rollback_to_version(user_id="u1", prompt_id=prompt_id, version_id=str(old_version["version_id"]))
    assert rolled is not None
    assert rolled["title"] == old_version["title"]
