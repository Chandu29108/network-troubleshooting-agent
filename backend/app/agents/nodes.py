"""
Node functions for the multi-agent LangGraph. Each node takes the shared
AgentState, does one job, and returns a partial state update — this is the
LangGraph pattern that keeps agents composable and independently testable.

Design: separate Router / Diagnostic / Retrieval / Synthesis agents rather
than one big prompt, because each has a distinct job (classify vs. gather
evidence via tools vs. search docs vs. write the final answer) and this lets
us swap/tune/test any one of them without touching the others — the core
reason to use a graph instead of a single call.
"""
from typing import Literal, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agents.prompts import (
    DIAGNOSTIC_AGENT_PROMPT,
    GENERAL_PROMPT,
    ROUTER_PROMPT,
    SYNTHESIS_PROMPT,
)
from app.config import get_settings
from app.core.logging_config import logger
from app.core.resilience import astream_with_retry_and_fallback, invoke_with_retry_and_fallback
from app.rag.retriever import retrieve_relevant_docs
from app.tools.log_parser import parse_router_log
from app.tools.network_tools import NETWORK_TOOLS

settings = get_settings()

ALL_TOOLS = [*NETWORK_TOOLS, parse_router_log]
TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}


class AgentState(TypedDict, total=False):
    user_message: str
    history: list[dict]          # prior turns: [{"role": "user"/"assistant", "content": ...}]
    route: Literal["diagnostic", "general"]
    diagnosis: str
    retrieved_docs: list[dict]
    final_answer: str


def _llm(temperature: float = 0.2, model_name: str | None = None) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=model_name or settings.gemini_model,
        google_api_key=settings.google_api_key,
        temperature=temperature,
        timeout=30,       # fail loudly after 30s instead of hanging silently
        max_retries=1,    # don't let internal auto-retry compound the wait
    )


def _llm_pair(temperature: float) -> tuple[ChatGoogleGenerativeAI, ChatGoogleGenerativeAI]:
    """Primary model + a fallback on a separate capacity pool, used together
    via invoke_with_retry_and_fallback / astream_with_retry_and_fallback."""
    return _llm(temperature), _llm(temperature, model_name=settings.gemini_fallback_model)


def _history_to_messages(history: list[dict] | None, limit: int = 12) -> list:
    """
    Converts stored {"role": "user"/"assistant", "content": ...} turns into
    LangChain messages, so prior turns actually reach the LLM instead of
    just sitting unused in AgentState. `limit` caps how many prior turns
    are replayed, to bound token usage on long conversations.
    """
    if not history:
        return []
    trimmed = history[-limit:]
    messages: list = []
    for turn in trimmed:
        role = turn.get("role")
        content = turn.get("content", "")
        if not content:
            continue
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    return messages


def _extract_text(content) -> str:
    """
    Gemini 3.x "thinking" models return `.content` as a list of content
    blocks (e.g. {"type": "text", "text": "..."} alongside "thinking"
    blocks) instead of a plain string. This normalizes either shape into
    plain text, skipping non-text blocks, so the rest of the pipeline can
    keep treating message content as a simple string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content) if content else ""


def router_node(state: AgentState) -> dict:
    logger.info("[router_node] classifying message")
    llm, fallback_llm = _llm_pair(temperature=0)
    prompt = ROUTER_PROMPT.format(message=state["user_message"])
    history_messages = _history_to_messages(state.get("history"))
    messages = [*history_messages, HumanMessage(content=prompt)]
    response = invoke_with_retry_and_fallback(llm.invoke, fallback_llm.invoke, messages)
    label = _extract_text(response.content).strip().lower()
    route = "diagnostic" if "diagnostic" in label else "general"
    logger.info("[router_node] route=%s", route)
    return {"route": route}


def diagnostic_node(state: AgentState) -> dict:
    """
    Runs a small tool-calling loop: ask the LLM what it wants to do, execute
    any tool calls it requests, feed results back, and repeat (capped) until
    it produces a plain-text diagnosis instead of another tool call.
    """
    logger.info("[diagnostic_node] starting tool-calling loop")
    llm, fallback_llm = _llm_pair(temperature=0.2)
    llm = llm.bind_tools(ALL_TOOLS)
    fallback_llm = fallback_llm.bind_tools(ALL_TOOLS)
    prompt = DIAGNOSTIC_AGENT_PROMPT.format(message=state["user_message"])
    history_messages = _history_to_messages(state.get("history"))
    messages: list = [
        SystemMessage(content=prompt),
        *history_messages,
        HumanMessage(content=state["user_message"]),
    ]

    for _step in range(3):  # hard cap prevents infinite tool-call loops
        ai_msg: AIMessage = invoke_with_retry_and_fallback(
            llm.invoke, fallback_llm.invoke, messages
        )
        messages.append(ai_msg)

        if not ai_msg.tool_calls:
            return {"diagnosis": _extract_text(ai_msg.content)}

        for call in ai_msg.tool_calls:
            tool_fn = TOOLS_BY_NAME.get(call["name"])
            if tool_fn is None:
                result = f"Unknown tool: {call['name']}"
            else:
                logger.info("[diagnostic_node] calling tool %s(%s)", call["name"], call["args"])
                result = tool_fn.invoke(call["args"])
            messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))

    # Fallback if the loop cap is hit without a final text answer
    if not messages:
        return {"diagnosis": "Unable to complete diagnosis."}
    return {"diagnosis": _extract_text(messages[-1].content)}


def retrieval_node(state: AgentState) -> dict:
    query = state.get("diagnosis") or state["user_message"]
    logger.info("[retrieval_node] searching knowledge base")
    docs = retrieve_relevant_docs(query, k=4)
    logger.info("[retrieval_node] found %d chunks", len(docs))
    return {"retrieved_docs": docs}


def _format_context(docs: list[dict]) -> str:
    if not docs:
        return "(no relevant internal documentation found)"
    return "\n\n".join(f"[Source: {d['source']}]\n{d['content']}" for d in docs)


async def synthesis_node(state: AgentState) -> dict:
    """
    Produces the final answer. This node is intentionally the one whose
    LLM call the API layer streams token-by-token to the frontend, since
    it's the user-facing output.
    """
    logger.info("[synthesis_node] generating final answer, route=%s", state.get("route"))
    llm, fallback_llm = _llm_pair(temperature=0.3)
    context = _format_context(state.get("retrieved_docs", []))

    if state.get("route") == "diagnostic":
        prompt = SYNTHESIS_PROMPT.format(
            diagnosis=state.get("diagnosis", ""),
            context=context,
            message=state["user_message"],
        )
    else:
        prompt = GENERAL_PROMPT.format(context=context, message=state["user_message"])

    history_messages = _history_to_messages(state.get("history"))
    stream_messages = [*history_messages, HumanMessage(content=prompt)]
    full_response = ""
    async for chunk in astream_with_retry_and_fallback(
        lambda: llm.astream(stream_messages),
        lambda: fallback_llm.astream(stream_messages),
    ):
        full_response += _extract_text(chunk.content)
    return {"final_answer": full_response}


def route_decision(state: AgentState) -> str:
    """Conditional-edge function: general questions skip the diagnostic/tool step."""
    return "diagnostic" if state.get("route") == "diagnostic" else "general"