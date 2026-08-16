"""Tests for Cortex Hub agents and API."""

from unittest.mock import MagicMock, patch

from backend.hub.agents.cortex import resolve_agent, run_hub_chat
from backend.hub.agents.session_rag import clear_session, ingest_upload, retrieve


def test_resolve_agent_manual_coding():
    agent, trace = resolve_agent("coding", prompt="fix the router")
    assert agent == "coding"
    assert trace[0] == "manual:coding"


def test_resolve_agent_session_pdf_followup():
    agent, trace = resolve_agent("auto", prompt="what is chapter 2 about?", has_session_pdf=True)
    assert agent == "pdf_rag"
    assert "session:pdf" in trace[0]


def test_session_rag_ingest_and_retrieve():
    sid = "pytest-session"
    clear_session(sid)
    n = ingest_upload(sid, "t.txt", b"numpy arrays linear algebra eigenvalues", "text/plain")
    assert n >= 1
    hits = retrieve(sid, "eigenvalues", top_k=2)
    assert hits
    clear_session(sid)


@patch("backend.hub.agents.cortex.run_study_specialist")
@patch("backend.hub.agents.cortex.resolve_agent")
def test_run_hub_chat_study_agent(mock_resolve, mock_study):
    mock_resolve.return_value = ("study", ["manual:study"])
    mock_study.return_value = ("Open /lecture-notes", [])
    db = MagicMock()
    result = run_hub_chat(
        db=db,
        user_id=1,
        hub_context={"lecture_notes": {"count": 2, "recent_titles": ["numpy"]}},
        messages=[{"role": "user", "content": "numpy lecture"}],
        agent="study",
    )
    assert result.agent_used == "study"
    assert "lecture-notes" in result.reply.lower() or "Lecture Notes" in result.reply
