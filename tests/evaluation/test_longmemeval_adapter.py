import pytest

from tests.evaluation import longmemeval_adapter as lme


class _FakeResponse:
    status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return {"choices": [{"message": {"content": "CORRECT"}}]}


class _FakeJudgeSession:
    def post(self, *args, **kwargs):
        return _FakeResponse()


class _FakeAgentResponse:
    def __init__(self, status=200, body=None, json_error=None):
        self.status = status
        self._body = body or {
            "response": "ok",
            "tool_calls": [{"name": "memory_search"}],
            "verbose_data": {
                "tool_events": [
                    {"type": "tool_result", "name": "memory_search", "content": "hit"}
                ]
            },
        }
        self._json_error = json_error

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        if self._json_error:
            raise self._json_error
        return self._body

    async def text(self):
        return str(self._body)


class _FakeAgentSession:
    def __init__(self, response=None, error=None):
        self.payload = None
        self.response = response or _FakeAgentResponse()
        self.error = error

    def post(self, *args, **kwargs):
        if self.error:
            raise self.error
        self.payload = kwargs.get("json")
        return self.response


def test_fuzzy_match_rejects_numeric_substring_false_positive():
    assert not lme._fuzzy_match(4, "I baked 14 times in the past two weeks.")


def test_longmemeval_synthesis_import_works_when_adapter_runs_as_script(monkeypatch):
    import importlib
    import sys
    from pathlib import Path

    module = sys.modules.pop("longmemeval_synthesis", None)
    monkeypatch.syspath_prepend(str(Path(__file__).parent))
    try:
        imported = importlib.import_module("longmemeval_synthesis")
        assert imported.synthesize_answer("How many kits?", []) is None
    finally:
        if module is not None:
            sys.modules["longmemeval_synthesis"] = module


def test_fuzzy_match_rejects_conflicting_currency_false_positive():
    response = "I found conflicting records, but the reliable amount is $350,000."

    assert not lme._fuzzy_match("$400,000", response)


def test_fuzzy_match_rejects_mentioned_but_not_selected_currency():
    response = (
        "Some records show $350,000 and others show $400,000. "
        "Since you told me directly that the amount was $350,000, that's the reliable source."
    )

    assert not lme._fuzzy_match("$400,000", response)


def test_fuzzy_match_rejects_goal_time_as_personal_best():
    response = "Your personal best is 27:12. The time 25:50 is the goal you hope to beat."

    assert not lme._fuzzy_match("25 minutes and 50 seconds (or 25:50)", response)


def test_fuzzy_match_rejects_location_contradiction():
    assert not lme._fuzzy_match("the suburbs", "Rachel moved to Chicago.")


def test_fuzzy_match_rejects_stopword_overlap_for_short_answer():
    assert not lme._fuzzy_match("the suburbs", "Chicago is the answer.")


def test_fuzzy_match_accepts_equivalent_number_word():
    assert lme._fuzzy_match("four", "You tried 4 Korean restaurants.")


@pytest.mark.asyncio
async def test_send_message_can_return_verbose_details():
    session = _FakeAgentSession()

    result = await lme.send_message(
        session,
        "question",
        user_id="u",
        workspace_id="w",
        return_details=True,
    )

    assert session.payload["verbose"] is True
    assert "Use memory_search before answering" in session.payload["message"]
    assert result["response"] == "ok"
    assert result["http_status"] == 200
    assert result["error"] is None
    assert result["tool_calls"] == [{"name": "memory_search"}]
    assert result["tool_events"][0]["content"] == "hit"


@pytest.mark.asyncio
async def test_send_message_records_non_200_diagnostics():
    session = _FakeAgentSession(response=_FakeAgentResponse(status=503, body="unavailable"))

    result = await lme.send_message(
        session,
        "question",
        user_id="u",
        workspace_id="w",
        return_details=True,
    )

    assert result["response"] == ""
    assert result["http_status"] == 503
    assert result["error"] == "http_503"
    assert "unavailable" in result["raw_body"]


@pytest.mark.asyncio
async def test_send_message_records_exception_diagnostics():
    session = _FakeAgentSession(error=TimeoutError("slow"))

    result = await lme.send_message(
        session,
        "question",
        user_id="u",
        workspace_id="w",
        return_details=True,
    )

    assert result["response"] == ""
    assert result["http_status"] is None
    assert result["error"] == "TimeoutError: slow"


@pytest.mark.asyncio
async def test_score_response_strict_guard_overrides_bad_judge():
    result = await lme.score_response(
        "$400,000",
        "The pre-approval amount was $350,000.",
        _FakeJudgeSession(),
    )

    assert result is False


@pytest.mark.asyncio
async def test_run_single_question_records_debug_fields(monkeypatch):
    async def fake_ingest(session, haystack_sessions, user_id, workspace_id="personal"):
        return 2

    async def fake_send(
        session, message, user_id=lme.USER_ID, workspace_id="personal", return_details=False
    ):
        return {
            "response": "answer",
            "tool_calls": [{"name": "memory_search"}],
            "tool_events": [{"name": "memory_search", "content": "snippet"}],
            "http_status": 200,
            "error": None,
            "raw_body": "",
        }

    monkeypatch.setattr(lme, "ingest_sessions_fast", fake_ingest)
    monkeypatch.setattr(lme, "send_message", fake_send)

    result = await lme.run_single_question(
        {
            "question_id": "qid",
            "question_type": "knowledge-update",
            "question": "Where did Rachel move?",
            "answer": "the suburbs",
            "haystack_sessions": [[{"role": "user", "content": "hello"}]],
        },
        session=None,
        judge_session=None,
        idx=3,
        total=5,
    )

    assert result["question"] == "Where did Rachel move?"
    assert result["user_id"] == "lme_eval_user_3"
    assert result["workspace_id"] == "lme_eval_3"
    assert result["scorer"] == "fuzzy"
    assert result["agent_response_full"] == "answer"
    assert result["tool_calls"] == [{"name": "memory_search"}]
    assert result["tool_events"] == [{"name": "memory_search", "content": "snippet"}]
    assert result["http_status"] == 200
    assert result["error"] is None


@pytest.mark.asyncio
async def test_run_single_question_uses_deterministic_synthesis(monkeypatch):
    async def fake_ingest(session, haystack_sessions, user_id, workspace_id="personal"):
        return 2

    async def fake_send(
        session, message, user_id=lme.USER_ID, workspace_id="personal", return_details=False
    ):
        return {
            "response": "Found 10 conversation matches:\n- raw search output",
            "tool_calls": [{"name": "memory_search"}],
            "tool_events": [
                {
                    "tool": "memory_search",
                    "stage": "end",
                    "output": "Model kits mentioned: 1. Gundam 2. Spitfire 3. Titanic",
                }
            ],
            "http_status": 200,
            "error": None,
            "raw_body": "",
        }

    monkeypatch.setattr(lme, "ingest_sessions_fast", fake_ingest)
    monkeypatch.setattr(lme, "send_message", fake_send)

    result = await lme.run_single_question(
        {
            "question_id": "qid",
            "question_type": "multi-session",
            "question": "How many model kits have I worked on or bought?",
            "answer": "3",
            "haystack_sessions": [[{"role": "user", "content": "hello"}]],
        },
        session=None,
        judge_session=None,
        idx=1,
        total=1,
    )

    assert result["agent_response_full"] == "3"
    assert result["synthesis"] == "deterministic"
    assert result["correct"] is True
