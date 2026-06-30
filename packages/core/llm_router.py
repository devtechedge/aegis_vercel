# packages/core/llm_router.py
import os
from functools import lru_cache
from langchain_core.language_models.chat_models import BaseChatModel

def _has(key: str) -> bool:
    return bool(os.getenv(key))

@lru_cache
def get_llm(task: str = "fast") -> BaseChatModel:
    """
    LLM Router with fallbacks.
    fast -> gpt-4o-mini / gemini-1.5-flash
    reasoning -> gpt-4o
    coding -> claude-3.5-sonnet
    Vercel-safe: falls back to FakeListChatModel if no keys / missing packages
    """
    # If no keys at all, use Fake
    if not (_has("OPENAI_API_KEY") or _has("ANTHROPIC_API_KEY") or _has("GOOGLE_API_KEY")):
        from langchain_core.language_models.fake_chat_models import FakeListChatModel
        return FakeListChatModel(responses=[
            '{"next": "knowledge", "reasoning": "fake routing – set GOOGLE_API_KEY for free inference"}',
            "AEGIS response (offline fake model – set GOOGLE_API_KEY at https://aistudio.google.com/app/apikey for free live inference).",
        ] * 50)

    models = []
    # Primary routing – each wrapped in try/except for missing packages
    try:
        if task == "coding" and _has("ANTHROPIC_API_KEY"):
            from langchain_anthropic import ChatAnthropic
            models.append(ChatAnthropic(model="claude-3-5-sonnet-20240620", temperature=0))
        elif task == "reasoning" and _has("OPENAI_API_KEY"):
            from langchain_openai import ChatOpenAI
            models.append(ChatOpenAI(model="gpt-4o", temperature=0))
        elif _has("OPENAI_API_KEY"):
            from langchain_openai import ChatOpenAI
            models.append(ChatOpenAI(model="gpt-4o-mini", temperature=0))
    except Exception:
        pass

    # Fallbacks – try each provider safely
    if _has("ANTHROPIC_API_KEY"):
        try:
            from langchain_anthropic import ChatAnthropic
            models.append(ChatAnthropic(model="claude-3-5-sonnet-20240620", temperature=0.1))
        except Exception:
            pass
    if _has("OPENAI_API_KEY"):
        try:
            from langchain_openai import ChatOpenAI
            models.append(ChatOpenAI(model="gpt-4o-mini", temperature=0))
        except Exception:
            pass
    if _has("GOOGLE_API_KEY"):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            models.append(ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0))
        except Exception as e:
            # langchain-google-genai not installed – will fall back to Fake
            pass

    if not models:
        from langchain_core.language_models.fake_chat_models import FakeListChatModel
        return FakeListChatModel(responses=[
            "AEGIS (mock – install langchain-google-genai or set OPENAI_API_KEY for live LLM)",
        ] * 50)

    primary = models[0]
    fallbacks = models[1:]
    if fallbacks:
        try:
            return primary.with_fallbacks(fallbacks)
        except Exception:
            return primary
    return primary

def bind_tools_safe(llm: BaseChatModel, tools: list):
    try:
        return llm.bind_tools(tools)
    except Exception:
        return llm
