"""Compiled LangGraph ``StateGraph`` for the prep pipeline.

Topology (fan-out then join then sequential keystone)::

    START ─┬─> fetch_cv ─> cv_analysis ─┐
           ├─> jd_analysis ─────────────┼─> gap_matching ─> question_planner ─> END
           └─> company_research ────────┘

``cv_analysis``, ``jd_analysis`` and ``company_research`` run concurrently. The
join into ``gap_matching`` uses a list ``start_key`` so LangGraph waits for all
three branches before running it — ``gap_matching`` reads ``candidate`` + ``job``,
while ``company`` finishes independently and is consumed by ``question_planner``
along with the gap analysis.

Deps are bound into each node with :func:`functools.partial` so the compiled node
presents the ``(state)`` signature LangGraph invokes.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from langgraph.graph import END, START, StateGraph

from . import nodes
from .state import PrepState

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

    from ..core.deps import Deps


def build_prep_graph(deps: Deps) -> CompiledStateGraph:
    """Build and compile the prep ``StateGraph`` with ``deps`` bound into nodes."""
    graph: StateGraph = StateGraph(PrepState)

    graph.add_node("fetch_cv", partial(nodes.fetch_cv, deps=deps))
    graph.add_node("cv_analysis", partial(nodes.cv_analysis, deps=deps))
    graph.add_node("jd_analysis", partial(nodes.jd_analysis, deps=deps))
    graph.add_node("company_research", partial(nodes.company_research, deps=deps))
    graph.add_node("gap_matching", partial(nodes.gap_matching, deps=deps))
    graph.add_node("question_planner", partial(nodes.question_planner, deps=deps))

    # Fan-out: three independent branches start from START concurrently.
    graph.add_edge(START, "fetch_cv")
    graph.add_edge("fetch_cv", "cv_analysis")
    graph.add_edge(START, "jd_analysis")
    graph.add_edge(START, "company_research")

    # Join: gap_matching waits for candidate (cv) + job (jd) + company research.
    graph.add_edge(["cv_analysis", "jd_analysis", "company_research"], "gap_matching")

    # Sequential keystone then finish.
    graph.add_edge("gap_matching", "question_planner")
    graph.add_edge("question_planner", END)

    return graph.compile()
