# packages/core/llm_router.py
import os
from functools import lru_cache
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import RunnableConfig

def _has(key: str) -> bool:
    return bool(os.getenv(key))

@lru_cache
def get_llm(task: str = "fast") -> BaseChatModel:
    """
    LLM Router with fallbacks.
    fast -> gpt-4o-mini
    reasoning -> gpt-4o / o3-mini
    coding -> claude-3.5-sonnet
    """
    # Vercel-safe: if no keys, use Fake model
    if not _has("OPENAI_API_KEY") and not _has("ANTHROPIC_API_KEY") and not _has("GOOGLE_API_KEY"):
        from langchain_core.language_models.fake_chat_models import FakeListChatModel
        return FakeListChatModel(responses=[
            '{"next": "knowledge", "reasoning": "default fake routing"}',
            "AEGIS response (offline fake model - set OPENAI_API_KEY for real inference).",
        ] * 20)

    models = []
    # Primary routing
    if task == "coding" and _has("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic
        models.append(ChatAnthropic(model="claude-3-5-sonnet-20240620", temperature=0))
    elif task == "reasoning" and _has("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        models.append(ChatOpenAI(model="gpt-4o", temperature=0))
    elif _has("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        models.append(ChatOpenAI(model="gpt-4o-mini", temperature=0))

    # Fallbacks
    if _has("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic
        models.append(ChatAnthropic(model="claude-3-5-sonnet-20240620", temperature=0.1))
    if _has("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        models.append(ChatOpenAI(model="gpt-4o-mini", temperature=0))
    if _has("GOOGLE_API_KEY"):
        from langchain_google_genai import ChatGoogleGenerativeAI
        models.append(ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0))

    if not models:
        from langchain_core.language_models.fake_chat_models import FakeListChatModel
        return FakeListChatModel(responses=["fake"]*50)

    primary = models[0]
    fallbacks = models[1:]
    if fallbacks:
        return primary.with_fallbacks(fallbacks)
    return primary

def bind_tools_safe(llm: BaseChatModel, tools: list):
    try:
        return llm.bind_tools(tools)
    except Exception:
        return llm
