"""
Ghost v1.7.0 Temperament Demo.

This demo shows how the same Ghost relationship state can be
interpreted differently by different NPC temperament profiles.

Ghost does not choose actions.
Ghost does not generate dialogue.
Ghost exposes deterministic state.
External systems decide what to do with it.
"""

from ghost.api import GhostAPI
from ghost.events import RelationshipEvent, TemperamentPreset


def print_header(title):
    print()
    print("=" * 64)
    print(title)
    print("=" * 64)


def print_interpretation(packet):
    interp = packet["interpretation"]

    print(f"NPC:          {packet['npc']}")
    print(f"Temperament:  {packet['temperament']}")
    print(f"Relationship: {packet['relationship_state']}")
    print(f"Trust:        {packet['trust']:.3f}")
    print(f"Pressure:     {packet['pressure']}")
    print(f"Near break:   {packet['near_break']}")
    print(f"Event:        {packet['source_event']}")
    print()
    print("Interpretation:")
    print(f"  emotional_read: {interp['emotional_read']}")
    print(f"  stance:         {interp['stance']}")
    print(f"  fear:           {interp['fear']:.3f}")
    print(f"  suspicion:      {interp['suspicion']:.3f}")
    print(f"  anger:          {interp['anger']:.3f}")
    print(f"  confidence:     {interp['confidence']:.3f}")
    print(f"  loyalty:        {interp['loyalty']:.3f}")
    print(f"  relief:         {interp['relief']:.3f}")
    print(f"  intensity:      {interp['intensity']:.3f}")


def main():
    print_header("GHOST TEMPERAMENT DEMO")

    print("This demo uses GhostAPI plus the public v1.7 temperament layer.")
    print()
    print("The same relationship event is interpreted through different")
    print("NPC temperament profiles.")
    print()
    print("Ghost exposes state. Your game decides what happens next.")

    api = GhostAPI()

    print_header("Step 1: Create a relationship break")

    relationship = api.engine.apply_event(
        "player",
        "shopkeeper",
        RelationshipEvent.BETRAYAL,
    )

    diagnostics = relationship["diagnostics"]

    print(f"Event:        {diagnostics['event']}")
    print(f"State:        {relationship['state']}")
    print(f"Trust:        {relationship['trust']:.3f}")
    print(f"Pressure:     {diagnostics['pressure']}")
    print(f"Severity:     {diagnostics['severity']:.3f}")
    print(f"Near break:   {diagnostics['near_break']}")

    print_header("Step 2: Interpret same state through different temperaments")

    temperament_map = [
        ("calm_guard", TemperamentPreset.CALM),
        ("anxious_guard", TemperamentPreset.ANXIOUS),
        ("confident_guard", TemperamentPreset.CONFIDENT),
        ("suspicious_guard", TemperamentPreset.SUSPICIOUS),
        ("resentful_guard", TemperamentPreset.RESENTFUL),
        ("loyal_guard", TemperamentPreset.LOYAL),
        ("volatile_guard", TemperamentPreset.VOLATILE),
    ]

    for npc, temperament in temperament_map:
        packet = api.interpret_relationship_packet(
            npc=npc,
            relationship=relationship,
            temperament=temperament,
        )

        print()
        print("-" * 64)
        print_interpretation(packet)

    print_header("Step 3: Same engine state, different external outcomes")

    print("Ghost did not pick an action.")
    print("Ghost did not write dialogue.")
    print("Ghost did not decide combat, forgiveness, or pricing.")
    print()
    print("It only exposed deterministic interpretation metadata.")
    print()
    print("An external game layer could now decide:")
    print("  anxious_guard    -> avoid / call help")
    print("  confident_guard  -> confront")
    print("  suspicious_guard -> restrict access")
    print("  resentful_guard  -> escalate")
    print("  loyal_guard      -> hesitate")
    print("  volatile_guard   -> overreact")

    print()
    print("✔ Ghost temperament demo complete")


if __name__ == "__main__":
    main()
