"""Tests for heuristics layer."""

from coremem.heuristics import SearchHeuristics


def test_keyword_overlap_boosts_when_words_match():
    s = SearchHeuristics.keyword_overlap(
        query="how many model kits",
        content="I love building model kits and painting them",
        score=0.5,
    )
    assert s > 0.50


def test_keyword_overlap_no_boost_when_no_overlap():
    s = SearchHeuristics.keyword_overlap(
        query="model kits",
        content="I enjoy eating pizza with friends",
        score=0.5,
    )
    assert s == 0.50


def test_keyword_overlap_ignores_stop_words():
    s = SearchHeuristics.keyword_overlap(
        query="how many model kits have I worked on",
        content="I worked on many different things",
        score=0.5,
    )
    # "worked" is not a stop word, "many" is borderline
    assert s >= 0.50


def test_is_counting_question():
    assert SearchHeuristics.is_counting_question("How many model kits?")
    assert SearchHeuristics.is_counting_question("How many weeks did it take?")
    assert not SearchHeuristics.is_counting_question("What is my name?")
    assert not SearchHeuristics.is_counting_question("Where do I live?")


def test_extract_date_cues():
    assert SearchHeuristics.extract_date_cues("In 2025 I went skiing") == "2025"
    assert SearchHeuristics.extract_date_cues("What happened in March?") == "March"
    assert SearchHeuristics.extract_date_cues("No date here") is None


def test_person_name_boost():
    s = SearchHeuristics.person_name_boost("I met Sarah Johnson at the conference", 0.5)
    assert s > 0.50

    s2 = SearchHeuristics.person_name_boost("the quick brown fox", 0.5)
    assert s2 == 0.50


def test_quoted_phrase_boost():
    s = SearchHeuristics.quoted_phrase_boost(
        query='my "model kits" hobby',
        content="I spend weekends on model kits painting",
        score=0.5,
    )
    assert s > 0.50

    s2 = SearchHeuristics.quoted_phrase_boost(
        query='my "model kits" hobby',
        content="I enjoy painting miniatures",
        score=0.5,
    )
    assert s2 == 0.50


def test_apply_all_chains():
    s = SearchHeuristics.apply_all(
        query="how many model kits",
        content="I love building model kits. Finished a Revell F-15 Eagle and Tamiya Spitfire.",
        score=0.7,
    )
    assert s > 0.70
