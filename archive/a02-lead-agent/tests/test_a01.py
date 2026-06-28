"""A01 验收测试：ThreadState reducer + 最小状态图。"""

import pytest

from deerflow_harness.lead_agent import make_lead_agent
from deerflow_harness.thread_state import (
    ThreadState,
    merge_artifacts,
    merge_promoted,
    merge_sandbox,
    merge_viewed_images,
)


class TestReducers:
    def test_merge_artifacts_deduplicates_and_preserves_order(self):
        assert merge_artifacts(["a.md", "b.md"], ["b.md", "c.md"]) == [
            "a.md",
            "b.md",
            "c.md",
        ]

    def test_merge_artifacts_handles_none(self):
        assert merge_artifacts(None, ["x.md"]) == ["x.md"]
        assert merge_artifacts(["x.md"], None) == ["x.md"]

    def test_merge_sandbox_allows_idempotent_writes(self):
        s1 = {"sandbox_id": "local:thread-1"}
        s2 = {"sandbox_id": "local:thread-1"}
        assert merge_sandbox(s1, s2) == s1

    def test_merge_sandbox_rejects_conflicting_ids(self):
        s1 = {"sandbox_id": "local:thread-1"}
        s2 = {"sandbox_id": "local:thread-2"}
        with pytest.raises(ValueError, match="Conflicting sandbox state"):
            merge_sandbox(s1, s2)

    def test_merge_viewed_images_empty_dict_clears(self):
        existing = {"img1": {"base64": "abc", "mime_type": "image/png"}}
        assert merge_viewed_images(existing, {}) == {}

    def test_merge_viewed_images_merges(self):
        a = {"img1": {"base64": "a", "mime_type": "image/png"}}
        b = {"img2": {"base64": "b", "mime_type": "image/jpeg"}}
        merged = merge_viewed_images(a, b)
        assert "img1" in merged and "img2" in merged

    def test_merge_promoted_scoped_by_catalog_hash(self):
        old = {"catalog_hash": "h1", "names": ["t1"]}
        same = {"catalog_hash": "h1", "names": ["t2"]}
        assert merge_promoted(old, same) == {
            "catalog_hash": "h1",
            "names": ["t1", "t2"],
        }

        new_hash = {"catalog_hash": "h2", "names": ["t3"]}
        assert merge_promoted(old, new_hash) == {
            "catalog_hash": "h2",
            "names": ["t3"],
        }


class TestStateGraph:
    def test_make_lead_agent_compiles_and_invokes(self):
        graph = make_lead_agent()
        result = graph.invoke({"messages": []})

        assert len(result["messages"]) == 1
        assert result["messages"][0].content == "A01 state graph is running."
        assert "a01-output.md" in result["artifacts"]

    def test_thread_state_accepts_custom_fields(self):
        state: ThreadState = {
            "messages": [],
            "sandbox": {"sandbox_id": "local:abc"},
            "thread_data": {
                "workspace_path": "/mnt/user-data/workspace",
                "uploads_path": "/mnt/user-data/uploads",
                "outputs_path": "/mnt/user-data/outputs",
            },
            "artifacts": [],
            "viewed_images": {},
            "promoted": None,
        }
        assert state["sandbox"]["sandbox_id"] == "local:abc"
