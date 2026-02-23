from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, StateGraph
try:
    # Optional: attach Langfuse callback to LangChain/LangGraph if available
    from langfuse.callbacks import CallbackHandler as LangfuseCallbackHandler  # type: ignore
except Exception:  # pragma: no cover
    LangfuseCallbackHandler = None  # type: ignore

from app.config import AppSettings
from app.graph.state import ResearchState
from app.graph.nodes.start import start_node
from app.graph.nodes.data_collection import data_collection_node
from app.graph.nodes.news_sentiment import news_sentiment_node
from app.graph.nodes.youtube_analysis import youtube_analysis_node
from app.graph.nodes.technicals import technicals_node
from app.graph.nodes.comprehensive_fundamentals import comprehensive_fundamentals_node
from app.graph.nodes.peer_analysis import peer_analysis_node
from app.graph.nodes.analyst_recommendations import analyst_recommendations_node
from app.graph.nodes.cashflow import cashflow_node
from app.graph.nodes.leadership import leadership_node
from app.graph.nodes.sector_macro import sector_macro_node
from app.graph.nodes.growth_prospects import growth_prospects_node
from app.graph.nodes.valuation import valuation_node
from app.graph.nodes.filing_analysis import filing_analysis_node
from app.graph.nodes.earnings_call_analysis import earnings_call_analysis_node
from app.graph.nodes.strategic_conviction import strategic_conviction_node
from app.graph.nodes.sector_rotation import sector_rotation_node
from app.graph.nodes.synthesis import synthesis_node
from app.graph.nodes.synthesis_multi import enhanced_synthesis_node
from app.graph.nodes.enhanced_synthesis import synthesis_node as institutional_synthesis_node
from app.graph.nodes.conditional_synthesis import synthesis_node as conditional_synthesis_node


def _wrap(node_fn: Callable[[ResearchState, AppSettings], Any], settings: AppSettings):
    async def inner(state: ResearchState) -> ResearchState:
        return await node_fn(state, settings)

    return inner


def build_research_graph(settings: AppSettings):
    graph = StateGraph(ResearchState)

    graph.add_node("start", _wrap(start_node, settings))
    graph.add_node("data_collection", _wrap(data_collection_node, settings))
    graph.add_node("news_sentiment", _wrap(news_sentiment_node, settings))
    graph.add_node("youtube", _wrap(youtube_analysis_node, settings))
    graph.add_node("technicals", _wrap(technicals_node, settings))
    graph.add_node("fundamentals", _wrap(comprehensive_fundamentals_node, settings))
    graph.add_node("peer_analysis", _wrap(peer_analysis_node, settings))
    graph.add_node("analyst_recommendations", _wrap(analyst_recommendations_node, settings))
    graph.add_node("cashflow", _wrap(cashflow_node, settings))
    graph.add_node("leadership", _wrap(leadership_node, settings))
    graph.add_node("sector_macro", _wrap(sector_macro_node, settings))
    graph.add_node("growth_prospects", _wrap(growth_prospects_node, settings))
    graph.add_node("valuation", _wrap(valuation_node, settings))
    graph.add_node("filing_analysis", _wrap(filing_analysis_node, settings))
    graph.add_node("earnings_call_analysis", _wrap(earnings_call_analysis_node, settings))
    graph.add_node("strategic_conviction", _wrap(strategic_conviction_node, settings))
    graph.add_node("sector_rotation", _wrap(sector_rotation_node, settings))
    # Use conditional synthesis (chooses between institutional and standard)
    graph.add_node("synthesis", _wrap(conditional_synthesis_node, settings))

    graph.set_entry_point("start")
    graph.add_edge("start", "data_collection")
    
    # PARALLEL EXECUTION: All independent analyses run in parallel after data collection
    graph.add_edge("data_collection", "technicals")
    graph.add_edge("data_collection", "fundamentals")
    graph.add_edge("data_collection", "news_sentiment")
    graph.add_edge("data_collection", "youtube")
    graph.add_edge("data_collection", "filing_analysis")
    graph.add_edge("data_collection", "earnings_call_analysis")
    
    # DEPENDENT ANALYSES: These need specific data from previous steps
    graph.add_edge("fundamentals", "peer_analysis")
    graph.add_edge("peer_analysis", "analyst_recommendations")
    
    # CONVERGENCE POINT: All analyses converge to cashflow for synthesis
    graph.add_edge("technicals", "cashflow")
    graph.add_edge("analyst_recommendations", "cashflow")
    graph.add_edge("news_sentiment", "cashflow")
    graph.add_edge("youtube", "cashflow")
    graph.add_edge("filing_analysis", "cashflow")
    graph.add_edge("earnings_call_analysis", "cashflow")
    
    # OPTIMIZED PARALLEL EXECUTION: Run independent analyses in parallel
    # Leadership, sector_macro, and growth_prospects can run in parallel after cashflow
    graph.add_edge("cashflow", "leadership")
    graph.add_edge("cashflow", "sector_macro")
    graph.add_edge("cashflow", "growth_prospects")
    
    # Valuation needs growth_prospects, but can run in parallel with leadership/sector_macro
    graph.add_edge("growth_prospects", "valuation")
    
    # Strategic conviction and sector rotation can run in parallel after valuation
    graph.add_edge("valuation", "strategic_conviction")
    graph.add_edge("valuation", "sector_rotation")
    
    # Both converge to synthesis (LangGraph waits for all dependencies)
    graph.add_edge("strategic_conviction", "synthesis")
    graph.add_edge("sector_rotation", "synthesis")
    graph.add_edge("synthesis", END)

    compiled = graph.compile()
    # If Langfuse callback is available, we expose it on the compiled graph for callers to use.
    # We are not altering execution here to keep behavior unchanged.
    if LangfuseCallbackHandler is not None:
        setattr(compiled, "_langfuse_callback_cls", LangfuseCallbackHandler)
    return compiled
