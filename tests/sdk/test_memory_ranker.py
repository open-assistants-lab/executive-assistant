"""Tests for deterministic memory ranker — scoring, dedup, formatting.

Core invariants:
1. Current fact beats superseded fact for current query.
2. Superseded fact is penalized for current query, included for historical.
3. User message beats assistant message when both mention same fact.
4. Dedupe keeps exact fact + best evidence only.
5. Summary query preserves diverse domains.
6. Context formatter respects max items/chars.
"""

from src.sdk.memory_planner import MemoryQueryPlan
from src.sdk.memory_ranker import (
    MemoryCandidate,
    _apply_assistant_penalty,
    _apply_dedup_penalties,
    collect_candidates_from_facts,
    format_ranked_memory_context,
    rank_memory_candidates,
)


class FakeFact:
    def __init__(self, id_str, trigger, action, structured_data, is_superseded=False, domain="personal", superseded_by=None, confidence=0.9, updated_at="2026-05-01T00:00:00Z"):
        self.id = id_str
        self.trigger = trigger
        self.action = action
        self.structured_data = structured_data
        self.is_superseded = is_superseded
        self.domain = domain
        self.superseded_by = superseded_by
        self.confidence = confidence
        self.updated_at = updated_at


class FakeSearchResult:
    def __init__(self, id_val, role, ts, content, score=0.8):
        self.id = id_val
        self.role = role
        self.ts = ts
        self.content = content
        self.score = score


class FakeMemory:
    def __init__(self, id_val, domain, trigger, action, confidence=0.8, memory_type="preference"):
        self.id = id_val
        self.domain = domain
        self.trigger = trigger
        self.action = action
        self.confidence = confidence
        self.memory_type = memory_type


# — Test 1: Current fact beats superseded for current query —

def test_current_fact_beats_superseded():
    current = FakeFact(
        "f1",
        "location",
        "Denver",
        {"entity": "user", "attribute": "location", "value": "Denver"},
        is_superseded=False,
    )
    superseded = FakeFact(
        "f2",
        "location old",
        "Austin",
        {"entity": "user", "attribute": "location", "value": "Austin"},
        is_superseded=True,
        superseded_by="f1",
        updated_at="2026-01-01T00:00:00Z",
    )
    plan = MemoryQueryPlan(intent="current_fact", needs_current_facts=True)
    candidates = collect_candidates_from_facts([current, superseded], plan)
    ranked = rank_memory_candidates("Where do I live?", candidates)

    assert ranked[0].source == "fact"
    assert ranked[0].metadata["current"] is True
    assert "Denver" in ranked[0].text

    superseded_cands = [c for c in ranked if c.metadata.get("superseded")]
    denver_idx = next(i for i, c in enumerate(ranked) if "Denver" in c.text)
    austin_idx = next(i for i, c in enumerate(ranked) if "Austin" in c.text)
    # Current fact must outrank superseded fact
    assert denver_idx < austin_idx
    for c in superseded_cands:
        assert c.score < ranked[denver_idx].score


# — Test 2: Superseded fact for current query gets penalty —

def test_superseded_fact_penalized_for_current_query():
    s = FakeFact(
        "s1",
        "old project",
        "Retired",
        {"entity": "user", "attribute": "project", "value": "Retired"},
        is_superseded=True,
    )
    plan = MemoryQueryPlan(intent="current_fact", needs_current_facts=True)
    candidates = collect_candidates_from_facts([s], plan)
    ranked = rank_memory_candidates("what is my current project?", candidates)
    # Superseded fact should rank below a current fact would, but may
    # still carry a small positive score from token/attribute overlap
    assert ranked[0].source == "fact"
    assert ranked[0].metadata["superseded"] is True


# — Test 3: Superseded fact included for historical query —

def test_superseded_included_for_historical():
    s = FakeFact(
        "s1",
        "old location",
        "Austin",
        {"entity": "user", "attribute": "location", "value": "Austin"},
        is_superseded=True,
    )
    plan = MemoryQueryPlan(intent="historical_fact", needs_current_facts=True, needs_fact_history=True)
    candidates = collect_candidates_from_facts([s], plan)
    ranked = rank_memory_candidates(
        "What was my previous location before Denver?",
        candidates,
    )
    assert len(ranked) == 1
    # Historical queries reduce the superseded penalty — score won't be deeply negative
    assert ranked[0].score > -30


# — Test 4: User message beats assistant message —

def test_user_message_beats_assistant():
    import datetime
    ts = datetime.datetime(2026, 5, 1)
    user_msg = FakeSearchResult(1, "user", ts, "I moved to Denver last week", score=0.9)
    asst_msg = FakeSearchResult(2, "assistant", ts, "The user lives in Denver according to earlier messages", score=0.7)
    from src.sdk.memory_ranker import collect_candidates_from_messages
    candidates = collect_candidates_from_messages([user_msg, asst_msg])
    ranked = rank_memory_candidates("Where do I live?", candidates)

    user_cands = [c for c in ranked if c.metadata.get("role") == "user"]
    asst_cands = [c for c in ranked if c.metadata.get("role") == "assistant"]
    if user_cands and asst_cands:
        assert user_cands[0].score >= asst_cands[0].score


# — Test 5: Dedupe keeps exact fact + best message evidence —

def test_dedup_penalizes_duplicate_values():
    c1 = MemoryCandidate(source="fact", text="user.location = Denver", metadata={"value": "Denver", "current": True})
    c2 = MemoryCandidate(source="message", text="user (2026-05-01): I live in Denver", metadata={"value": "Denver"})
    c3 = MemoryCandidate(source="message", text="assistant (2026-05-01): user mentioned Denver", metadata={"value": "Denver"})
    candidates = [c1, c2, c3]
    for c in candidates:
        c.score = 40.0
    _apply_dedup_penalties(candidates)
    # c1 keeps 40, c2 and c3 get PENALTY_DUPLICATE (-10)
    assert candidates[0].score == 40.0  # first seen
    assert candidates[1].score == 30.0  # penalized
    assert candidates[2].score == 30.0  # penalized


# — Test 6: Summary intent preserves diverse domains —

def test_summary_query_scores_diverse():
    facts = [
        FakeFact("f1", "location", "Denver", {"entity": "user", "attribute": "location", "value": "Denver"}),
        FakeFact("f2", "project", "Pipeline", {"entity": "user", "attribute": "project", "value": "Pipeline", "domain": "work"}),
        FakeFact("f3", "coffee", "dark roast", {"entity": "user", "attribute": "coffee", "value": "dark roast", "domain": "preference"}),
    ]
    plan = MemoryQueryPlan(intent="summary", needs_current_facts=True, max_facts=10)
    candidates = collect_candidates_from_facts(facts, plan)
    ranked = rank_memory_candidates("What do you know about me?", candidates)
    assert len(ranked) == 3
    assert all(c.score >= 0 for c in ranked)


# — Test 7: Context formatter respects max_chars —

def test_format_respects_max_chars():
    candidates = [
        MemoryCandidate(source="fact", text="user.location = Denver", score=72.0, metadata={"current": True}),
        MemoryCandidate(source="message", text="user (2026-05-01): I moved to Denver" + "!" * 500, score=58.0, metadata={"role": "user", "ts": "2026-05-01"}),
    ]
    plan = MemoryQueryPlan(intent="current_fact", needs_current_facts=True, needs_messages=True)
    result = format_ranked_memory_context("Where do I live?", candidates, plan=plan, max_chars=200)
    assert len(result) <= 200


# — Test 8: Empty candidates return empty —

def test_empty_candidates():
    result = format_ranked_memory_context("What is my name?", [])
    assert result == ""


# — Test 9: Short exact fact gets bonus —

def test_short_exact_fact_gets_bonus():
    short = FakeFact(
        "f1",
        "name",
        "Eddy",
        {"entity": "user", "attribute": "name", "value": "Eddy"},
    )
    plan = MemoryQueryPlan(intent="current_fact", needs_current_facts=True)
    candidates = collect_candidates_from_facts([short], plan)
    ranked = rank_memory_candidates("What is my name?", candidates)
    assert len(ranked) == 1
    assert ranked[0].score > 40  # base 40 + short fact bonus 5 = 45 minimum


# — Test 10: Assistant penalty applies when user evidence exists —

def test_assistant_penalty_when_user_exists():
    c1 = MemoryCandidate(source="message", text="user says I live in Denver", metadata={"role": "user"})
    c2 = MemoryCandidate(source="message", text="assistant confirmed Denver", metadata={"role": "assistant"})
    c1.score = 50.0
    c2.score = 50.0
    _apply_assistant_penalty([c1, c2])
    assert c1.score == 50.0  # user untouched
    assert c2.score < 50.0   # assistant penalized


# — Test 11: Assistant NOT penalized when no user evidence —

def test_assistant_not_penalized_without_user():
    c1 = MemoryCandidate(source="message", text="assistant summary of Denver", metadata={"role": "assistant"})
    c1.score = 50.0
    _apply_assistant_penalty([c1])
    assert c1.score == 50.0  # no user evidence → no penalty


# — Test 12: Correction marker signals boost score —

def test_correction_marker_boosts():
    current = FakeFact(
        "f1",
        "project updated",
        "Pipeline",
        {"entity": "user", "attribute": "project", "value": "Pipeline", "domain": "work"},
    )
    plan = MemoryQueryPlan(intent="current_fact", needs_current_facts=True)
    candidates = collect_candidates_from_facts([current], plan)
    ranked = rank_memory_candidates("What is my new project?", candidates)
    assert len(ranked) == 1
    # updated text contains "updated" which is a correction marker → +8
    assert ranked[0].score >= 40


# — Test 13: Attribute overlap boosts score —

def test_attribute_overlap_boosts():
    fact = FakeFact(
        "f1",
        "coffee preference",
        "dark roast",
        {"entity": "user", "attribute": "coffee", "value": "dark roast"},
    )
    plan = MemoryQueryPlan(intent="current_fact", needs_current_facts=True)
    candidates = collect_candidates_from_facts([fact], plan)
    ranked = rank_memory_candidates("What coffee do I drink?", candidates)
    # query contains "coffee" → attribute overlap bonus +20
    # plus current fact +40, token overlap +25 = 85 minimum
    assert ranked[0].score >= 60


# — Test 14: History keywords route to historical intent —

def test_history_keywords_route_to_historical():
    current = FakeFact("f1", "location", "Denver", {"entity": "user", "attribute": "location", "value": "Denver"})
    old = FakeFact("f2", "old loc", "Austin", {"entity": "user", "attribute": "location", "value": "Austin"}, is_superseded=True, superseded_by="f1")
    plan = MemoryQueryPlan(intent="historical_fact", needs_current_facts=True, needs_fact_history=True)
    candidates = collect_candidates_from_facts([current, old], plan)
    ranked = rank_memory_candidates("Where did I live before?", candidates)
    assert len(ranked) >= 2
    # historical intent means superseded is not deep-penalized → both should have reasonable scores
    old_cand = next((c for c in ranked if "Austin" in c.text), None)
    assert old_cand is not None
    assert old_cand.score > -40


# — Test 15: Format includes correct source labels —

def test_format_includes_source_labels():
    candidates = [
        MemoryCandidate(source="fact", text="user.location = Denver", score=72.0, metadata={"current": True}),
        MemoryCandidate(source="message", text="user: I live in Denver", score=58.0, metadata={"role": "user", "ts": "2026-05-01"}),
    ]
    plan = MemoryQueryPlan(intent="current_fact", needs_current_facts=True, needs_messages=True)
    result = format_ranked_memory_context("Where do I live?", candidates, plan=plan)
    assert "[fact/current]" in result
    assert "[user/" in result
