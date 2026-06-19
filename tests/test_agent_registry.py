import pytest

from ghost.engine import GhostEngine


def test_agent_creation_and_safe_public_reads():
    engine = GhostEngine()

    live_agent = engine.agents.ensure(" Alice ")

    live_agent["mood"] = 0.25

    read_agent = engine.agents.get("Alice")
    read_agent["mood"] = 999.0

    assert engine.agents.get("Alice")["mood"] == 0.25

    all_agents = engine.agents.all()
    all_agents["Alice"]["mood"] = 888.0

    assert engine.agents.get("Alice")["mood"] == 0.25

    assert live_agent["memory"] == {}


@pytest.mark.parametrize(
    "bad_id",
    [
        "",
        " ",
        "bad|id",
        None,
    ],
)
def test_agent_registry_rejects_invalid_ids(bad_id):
    engine = GhostEngine()

    with pytest.raises(ValueError):
        engine.agents.ensure(bad_id)
