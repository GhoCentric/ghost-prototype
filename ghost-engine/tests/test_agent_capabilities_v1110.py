import pytest

from ghost.agent import AgentRuntime


def test_capability_reads_are_copy_safe_and_registration_order_is_preserved():
    runtime = AgentRuntime()
    runtime.register_agent("sera", capabilities=["warn", "question"])
    capabilities = runtime.capabilities("sera")
    capabilities.append("corruption")
    assert runtime.capabilities("sera") == ["warn", "question"]


def test_add_capability_is_explicit_sorted_and_audited():
    runtime = AgentRuntime()
    runtime.register_agent("sera", capabilities=["warn", "question"])
    result = runtime.add_capability("sera", " confront ")
    assert result == {
        "agent_id": "sera",
        "capability_id": "confront",
        "before": ["warn", "question"],
        "after": ["confront", "question", "warn"],
    }
    assert runtime.capabilities("sera") == ["confront", "question", "warn"]


def test_add_capability_rejects_duplicate_normalized_id_without_mutation():
    runtime = AgentRuntime()
    runtime.register_agent("sera", capabilities=["question"])
    before = runtime.snapshot()
    with pytest.raises(ValueError, match="already registered"):
        runtime.add_capability("sera", " question ")
    assert runtime.snapshot() == before


def test_remove_capability_returns_true_then_false():
    runtime = AgentRuntime()
    runtime.register_agent("sera", capabilities=["question", "warn"])
    assert runtime.remove_capability("sera", " warn ") is True
    assert runtime.capabilities("sera") == ["question"]
    assert runtime.remove_capability("sera", "warn") is False


def test_capability_methods_require_registered_agent():
    runtime = AgentRuntime()
    for operation in (
        lambda: runtime.capabilities("missing"),
        lambda: runtime.add_capability("missing", "question"),
        lambda: runtime.remove_capability("missing", "question"),
    ):
        with pytest.raises(ValueError, match="agent is not registered"):
            operation()
