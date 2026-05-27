from tests.evaluation.longmemeval_synthesis import (
    _count_active_fact_items,
    _extract_duration_value,
    _is_only_conversation_echoes,
    synthesize_answer,
)


def _event(output: str, tool: str = "message_search") -> dict:
    return {"tool": tool, "stage": "end", "output": output}


def test_synthesizes_korean_restaurant_count_from_named_evidence():
    answer = synthesize_answer(
        "How many Korean restaurants have I tried in my city?",
        [
            _event(
                "I tried Seoul Garden, Kimchi House, Bulgogi Brothers, and Han River BBQ "
                "while looking for Korean restaurants in my city."
            )
        ],
    )
    assert answer == "4"


def test_synthesizes_model_kit_count_from_numbered_evidence():
    answer = synthesize_answer(
        "How many model kits have I worked on or bought?",
        [
            _event(
                "Model kits mentioned: 1. Gundam RX-78 2. Millennium Falcon "
                "3. Spitfire 4. Titanic 5. Porsche 911"
            )
        ],
    )
    assert answer == "5"


def test_synthesizes_clothing_item_count_from_comma_list():
    answer = synthesize_answer(
        "How many items of clothing do I need to pick up or return from various services?",
        [
            _event(
                "Clothing items to pick up or return: blazer, dress pants, winter coat, "
                "running shoes, blue dress, leather jacket."
            )
        ],
    )
    assert answer == "6"


def test_deduplicates_repeated_tool_events():
    output = (
        "Found 3 active facts:\n"
        "- user.completed_model_kits = ['F-15 Eagle', 'Spitfire'] (conf: 70%)\n"
        "- user.purchased_model_kits = ['B-29 bomber', '69 Camaro'] (conf: 75%)"
    )
    answer = synthesize_answer(
        "How many model kits have I worked on or bought?",
        [
            _event(output),
            _event(output),
        ],
    )
    assert answer == "4"


def test_returns_none_when_question_is_not_counting():
    assert synthesize_answer("Where did Rachel move?", [_event("Rachel moved to the suburbs")]) is None


def test_count_active_fact_items_from_list_values():
    text = (
        "Found 3 active facts:\n"
        "- user.completed_model_kits = ['Revell F-15 Eagle', 'Tamiya 1/48 Spitfire Mk.V'] (conf: 70%)\n"
        "- user.purchased_model_kits = ['1/72 scale B-29 bomber', \"1/24 scale '69 Camaro\"] (conf: 75%)\n"
        "- user.current_project = Tiger I tank (conf: 70%)"
    )
    assert _count_active_fact_items(text) == 4


def test_count_active_fact_items_single_scalar_facts():
    text = (
        "Found 2 active facts:\n"
        "- user.clothing_pickup = Need to pick up exchanged boots from Zara (conf: 70%)\n"
        "- user.business_plan = Planning streetwear clothing brand (conf: 70%)"
    )
    assert _count_active_fact_items(text) is None


def test_count_active_fact_items_uses_explicit_count():
    text = (
        "Found 4 active facts:\n"
        "- user.clothing_pickup = boots from Zara (conf: 75%)\n"
        "- user.clothing_pickup_items_count = 3 (conf: 70%)\n"
        "- user.business_plan = Planning streetwear clothing brand (conf: 75%)"
    )
    assert _count_active_fact_items(text) == 3


def test_count_active_fact_items_no_facts():
    assert _count_active_fact_items("Found 0 active facts:") is None
    assert _count_active_fact_items("no active facts at all") is None


def test_active_fact_synthesis_integration():
    answer = synthesize_answer(
        "How many model kits have I worked on or bought?",
        [
            _event(
                "Found 3 active facts:\n"
                "- user.completed_model_kits = ['Revell F-15 Eagle', 'Tamiya 1/48 Spitfire Mk.V'] (conf: 70%)\n"
                "- user.purchased_model_kits = ['1/72 scale B-29 bomber', \"1/24 scale '69 Camaro\"] (conf: 75%)\n"
                "- user.current_project = Tiger I tank (conf: 70%)"
            )
        ],
    )
    assert answer == "4"


def test_extract_duration_value_weeks():
    assert _extract_duration_value("user.marathon_time = 3.5 weeks (conf: 75%)") == "3.5 weeks"
    assert _extract_duration_value("It took 2 months to finish") == "2 months"
    assert _extract_duration_value("Spent 8 days camping") == "8 days"


def test_extract_duration_preserves_decimal():
    result = _extract_duration_value("user.marathon_time = 3.5 weeks")
    assert result == "3.5 weeks"


def test_extract_duration_no_value():
    assert _extract_duration_value("user.job_title = Senior Backend Engineer") is None
    assert _extract_duration_value("Found 5 conversation matches") is None


def test_duration_synthesis_integration():
    answer = synthesize_answer(
        "How many weeks did it take me to watch all the MCU movies and Star Wars films?",
        [
            _event(
                "Found 1 active facts:\n"
                "- user.marathon_time = 3.5 weeks (conf: 75%)\n"
                "Found 10 conversation matches"
            )
        ],
    )
    assert answer == "3.5 weeks"


def test_is_only_conversation_echoes_true():
    text = (
        "Found 10 conversation matches:\n"
        "- user (2026-05-07): How many items of clothing do I need to pick up? (score: 0.37)\n"
        "- user (2026-05-07): How many items of clothing? (score: 0.35)"
    )
    assert _is_only_conversation_echoes("How many items of clothing do I need to pick up or return?", text)


def test_is_only_conversation_echoes_false_with_facts():
    text = (
        "Found 3 active facts:\n"
        "- user.completed_model_kits = ['F-15 Eagle', 'Spitfire'] (conf: 70%)\n"
        "Found 10 conversation matches:\n"
        "- user (2026-05-07): blah (score: 0.37)"
    )
    assert not _is_only_conversation_echoes("How many model kits?", text)


def test_message_count_output_ignored():
    answer = synthesize_answer(
        "How many projects have I led or am currently leading?",
        [
            _event(
                "Searched 1 workspace(s): lme_eval_2\n"
                "Analyzed 164 sessions (164 raw matches)\n"
                "\nNo distinct items could be identified.",
                tool="message_count",
            )
        ],
    )
    assert answer is None


def test_conversation_match_echo_not_counted():
    answer = synthesize_answer(
        "How many items of clothing do I need to pick up or return?",
        [
            _event(
                "Found 10 conversation matches:\n"
                "- user (2026-05-07): How many items of clothing do I need to pick up? (score: 0.37)\n"
                "- user (2026-05-07): How many items of clothing? (score: 0.35)"
            )
        ],
    )
    assert answer is None


def test_factual_conversation_content_not_treated_as_echo():
    text = (
        "Found 9 conversation matches:\n"
        "- user (2026-05-06): I recently finished a simple Revell F-15 Eagle model and "
        "started a Tamiya 1/48 scale Spitfire Mk.V (score: 0.85)\n"
        "- user (2026-05-06): I'm looking for tips for my new 1/72 scale B-29 bomber (score: 0.72)"
    )
    assert not _is_only_conversation_echoes("How many model kits have I worked on or bought?", text)
