# packages/aegis_graph/state.py
from __future__ import annotations
from typing import Annotated, Any, Literal
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AegisState(BaseModel):
    """Supervisor state - Pydantic v2, LangGraph compatible"""
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)
    task: str = ""
    plan: list[str] = Field(default_factory=list)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    needs_human_approval: bool = False
    approval_payload: dict[str, Any] | None = None
    iteration: int = 0
    next_agent: str | None = None
    critic_feedback: str | None = None

    model_config = {"arbitrary_types_allowed": True}

# For LangGraph TypedDict compatibility
from typing import TypedDict
class GraphState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    task: str
    plan: list[str]
    artifacts: dict[str, Any]
    confidence: float
    needs_human_approval: bool
    approval_payload: dict[str, Any] | None
    iteration: int
    next_agent: str | None
    critic_feedback: str | None
