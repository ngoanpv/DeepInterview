"""Live-agent function tool: search the candidate's knowledge base (WP-8).

REQUIRES THE ``livekit`` EXTRA — this module imports ``livekit.agents`` at load time
and lives on the live voice path. It is deliberately NOT imported by
``deepinterview_agent.live.__init__`` (which imports only the livekit-free
``state`` module), so ``import deepinterview_agent.live.state`` keeps working with
the extra absent. The worker imports this lazily when wiring the live session.

RAG-delay pattern: knowledge lookups add latency on the turn path. Follow LiveKit's
recommended approach — emit a short filler line ("Let me check your prep notes…")
via the session before awaiting the lookup, so the candidate isn't met with dead
air while the sidecar responds. See LiveKit docs: "RAG" / `llm_node` enrichment.
"""

from __future__ import annotations

from livekit.agents import RunContext, function_tool

from ..core.adapters.knowledge import KnowledgeClient

# Cap how much grounded text we inject back into the live prompt (keep it lean).
_MAX_ANSWER_CHARS = 600


def make_search_knowledge_base(client: KnowledgeClient, user_id: str, lang: str = "en"):
    """Build the ``search_knowledge_base`` function tool bound to a client + user.

    The returned tool is registered on the live interviewer agent. It calls the
    knowledge sidecar and returns a short grounded string the model can speak.
    """

    @function_tool
    async def search_knowledge_base(context: RunContext, query: str) -> str:
        """Look up the candidate's prep materials to ground a follow-up or hint.

        Args:
            query: What to look up (a topic, competency, or the candidate's question).
        """
        # RAG-delay filler: optionally say a quick line here before the await, e.g.
        #   await context.session.say("Let me check your prep notes one second.")
        # so the lookup latency doesn't surface as silence on the turn path.
        answer, citations = await client.search(user_id, query, lang)
        if not answer:
            return "No relevant notes found in the candidate's knowledge base."
        sources = ", ".join(c.title for c in citations) if citations else "prep materials"
        grounded = answer[:_MAX_ANSWER_CHARS]
        return f"{grounded}\n\n(Sources: {sources})"

    return search_knowledge_base
