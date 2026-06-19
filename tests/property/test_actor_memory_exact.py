from collections import Counter

from hypothesis import given, strategies as st

from ghost.engine import GhostEngine
from ghost.ids import normalize_id


VALID_AGENT_IDS = st.text(
    alphabet=st.characters(
        blacklist_characters="|",
        blacklist_categories=("Cs",),
    ),
    min_size=1,
    max_size=5,
).filter(lambda value: value.strip() != "")


@given(
    actors=st.lists(VALID_AGENT_IDS, min_size=1, max_size=20)
)
def test_actor_threat_counts_match_events(actors):
    engine = GhostEngine()

    for actor in actors:
        engine.step(
            {
                "source": "npc_engine",
                "intent": "threat",
                "actor": actor,
                "intensity": 1.0,
            }
        )

    state = engine.state()
    memory = state["npc"]["actors"]

    normalized_counts = Counter(
        normalize_id(actor, "agent id")
        for actor in actors
    )

    for actor, expected_count in normalized_counts.items():
        assert memory[actor]["threat_count"] == expected_count
