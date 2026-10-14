from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver
from app.graph.state import AgentState
from app.graph.nodes import DentalGraphNodes
from app.graph.routing import route_by_intent


def create_study_graph(nodes: DentalGraphNodes, checkpointer: BaseCheckpointSaver = None):
    """
    Constructs and compiles the StateGraph workflow for the Student AI Assistant.
    """
    graph = StateGraph(AgentState)

    # 1. Register Nodes
    graph.add_node("load_context", nodes.load_context)
    graph.add_node("classify_query", nodes.classify_query)
    graph.add_node("tutor", nodes.tutor)
    graph.add_node("document_retrieval", nodes.document_retrieval)
    graph.add_node("web_research", nodes.web_research)
    graph.add_node("hybrid_retrieval", nodes.hybrid_retrieval)
    graph.add_node("study_tools", nodes.study_tools)
    graph.add_node("synthesize", nodes.synthesize)
    graph.add_node("verify_answer", nodes.verify_answer)
    graph.add_node("save_turn", nodes.save_turn)

    # 2. Sequential & Conditional Edges
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "classify_query")

    graph.add_conditional_edges(
        "classify_query",
        route_by_intent,
        {
            "tutor": "tutor",
            "document_retrieval": "document_retrieval",
            "web_research": "web_research",
            "hybrid_retrieval": "hybrid_retrieval",
            "study_tools": "study_tools",
        },
    )

    # Retrieval nodes feed into synthesis
    graph.add_edge("document_retrieval", "synthesize")
    graph.add_edge("web_research", "synthesize")
    graph.add_edge("hybrid_retrieval", "synthesize")

    # Direct nodes & synthesis feed into verification
    graph.add_edge("tutor", "verify_answer")
    graph.add_edge("study_tools", "verify_answer")
    graph.add_edge("synthesize", "verify_answer")

    graph.add_edge("verify_answer", "save_turn")
    graph.add_edge("save_turn", END)

    return graph.compile(checkpointer=checkpointer)


# Backwards compatibility alias
create_dental_graph = create_study_graph

