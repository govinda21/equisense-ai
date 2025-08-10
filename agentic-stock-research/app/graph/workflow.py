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
from app.graph.nodes.fundamentals import fundamentals_node
from app.graph.nodes.peer_analysis import peer_analysis_node
from app.graph.nodes.analyst_recommendations import analyst_recommendations_node
from app.graph.nodes.cashflow import cashflow_node
from app.graph.nodes.leadership import leadership_node
from app.graph.nodes.sector_macro import sector_macro_node
from app.graph.nodes.growth_prospects import growth_prospects_node
from app.graph.nodes.valuation import valuation_node
from app.graph.nodes.synthesis import synthesis_node


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
    graph.add_node("fundamentals", _wrap(fundamentals_node, settings))
    graph.add_node("peer_analysis", _wrap(peer_analysis_node, settings))
    graph.add_node("analyst_recommendations", _wrap(analyst_recommendations_node, settings))
    graph.add_node("cashflow", _wrap(cashflow_node, settings))
    graph.add_node("leadership", _wrap(leadership_node, settings))
    graph.add_node("sector_macro", _wrap(sector_macro_node, settings))
    graph.add_node("growth_prospects", _wrap(growth_prospects_node, settings))
    graph.add_node("valuation", _wrap(valuation_node, settings))
    graph.add_node("synthesis", _wrap(synthesis_node, settings))

    graph.set_entry_point("start")
    graph.add_edge("start", "data_collection")
    graph.add_edge("data_collection", "technicals")
    graph.add_edge("data_collection", "fundamentals")
    graph.add_edge("data_collection", "news_sentiment")
    graph.add_edge("data_collection", "youtube")
    
    # New integration: peer_analysis after fundamentals but before cashflow
    graph.add_edge("fundamentals", "peer_analysis")
    
    # New integration: analyst_recommendations after peer_analysis
    graph.add_edge("peer_analysis", "analyst_recommendations")
    
    # Updated flow: cashflow after analyst_recommendations
    graph.add_edge("technicals", "cashflow")
    graph.add_edge("analyst_recommendations", "cashflow")
    graph.add_edge("news_sentiment", "cashflow")
    graph.add_edge("youtube", "cashflow")
    
    graph.add_edge("cashflow", "leadership")
    graph.add_edge("leadership", "sector_macro")
    
    # New integration: growth_prospects after sector_macro
    graph.add_edge("sector_macro", "growth_prospects")
    
    # Enhanced valuation after growth_prospects
    graph.add_edge("growth_prospects", "valuation")
    graph.add_edge("valuation", "synthesis")
    graph.add_edge("synthesis", END)

    compiled = graph.compile()
    # If Langfuse callback is available, we expose it on the compiled graph for callers to use.
    # We are not altering execution here to keep behavior unchanged.
    if LangfuseCallbackHandler is not None:
        setattr(compiled, "_langfuse_callback_cls", LangfuseCallbackHandler)
    return compiled
