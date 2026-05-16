from src.sdk.knowledge_update import resolve_knowledge_update


def test_resolves_personal_best_time_not_goal_context():
    resolution = resolve_knowledge_update(
        "What was my personal best time in the charity 5K run?",
        [
            "I ran the charity 5K in 27:12 last year.",
            "I'm training for another charity 5K run and hoping to beat my personal best time of 25:50 this time around.",
        ],
    )

    assert resolution is not None
    assert resolution.recommended_value == "25:50"
    assert "personal best" in resolution.reason.lower()


def test_resolves_currency_from_direct_wells_fargo_support():
    resolution = resolve_knowledge_update(
        "What was the amount I was pre-approved for when I got my mortgage from Wells Fargo?",
        [
            "You were pre-approved for $350,000 from Wells Fargo when buying a $325,000 house.",
            "Remember when I got pre-approved for $400,000 from Wells Fargo?",
        ],
    )

    assert resolution is not None
    assert resolution.recommended_value == "$400,000"
    assert "$350,000" in resolution.rejected_values


def test_resolves_specific_relocation_over_broader_city():
    resolution = resolve_knowledge_update(
        "Where did Rachel move to after her recent relocation?",
        [
            "Rachel moved to Chicago, so we're deciding which neighborhoods to stay in.",
            "Rachel ended up moving to the suburbs after her recent relocation.",
        ],
    )

    assert resolution is not None
    assert resolution.recommended_value == "the suburbs"
    assert "Chicago" in resolution.rejected_values


def test_non_update_query_returns_none():
    assert resolve_knowledge_update("How many model kits have I bought?", ["I bought two kits."]) is None
