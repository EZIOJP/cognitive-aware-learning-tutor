"""Hub cortex request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HubChatMessage(BaseModel):
    role: str
    content: str


class HubChatRequest(BaseModel):
    messages: list[HubChatMessage] = Field(default_factory=list)
    agent: str = "auto"
    conversation_id: str | None = None
    llm_tier: str | None = None
    confirm_heavy_budget: bool = False


class HubChatResponse(BaseModel):
    reply: str
    agent_used: str
    source: str = "gemma"
    llm_available: bool = True
    trace: list[str] = Field(default_factory=list)
    rag_sources: list[str] = Field(default_factory=list)


class HubAgentInfo(BaseModel):
    id: str
    label: str
    description: str


HUB_AGENTS: list[HubAgentInfo] = [
    HubAgentInfo(id="auto", label="Auto", description="Route by intent or attachment"),
    HubAgentInfo(id="chat", label="Chat", description="Study coach with hub context"),
    HubAgentInfo(id="coding", label="Coding", description="Project agent + codebase"),
    HubAgentInfo(id="corpus", label="Corpus", description="Persistent lecture/textbook RAG"),
    HubAgentInfo(id="search", label="Search", description="Web search then coach answer"),
    HubAgentInfo(id="pdf_rag", label="PDF", description="Ephemeral upload Q&A"),
    HubAgentInfo(id="study", label="Study", description="Topic study flow suggestions"),
]
