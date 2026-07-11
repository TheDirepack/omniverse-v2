from langgraph.graph import END, StateGraph

from app.agents.nodes import (
    db_integrator_node,
    extrapolation_node,
    manager_node,
    mark_explored_node,
    research_node,
    summary_node,
)
from app.agents.workflow_state import OmniverseState
from app.core.enums import RunPhase


def create_workflow():
    workflow = StateGraph(OmniverseState)

    # Add Nodes
    workflow.add_node("research", research_node)
    workflow.add_node("db_integrator", db_integrator_node)
    workflow.add_node("mark_explored", mark_explored_node)
    workflow.add_node("summary", summary_node)
    workflow.add_node("manager", manager_node)
    workflow.add_node("extrapolation", extrapolation_node)

    # Set Entry Point
    workflow.set_entry_point("research")

    # Define Edges
    workflow.add_edge("research", "db_integrator")
    workflow.add_edge("db_integrator", "mark_explored")
    workflow.add_edge("mark_explored", "summary")
    workflow.add_edge("summary", END)

    # Conditional Routing from Manager
    workflow.add_conditional_edges(
        "manager",
        lambda state: state["active_task"],
        {
            RunPhase.RESEARCH: "research",
            RunPhase.DB_INTEGRATION: "db_integrator",
            RunPhase.SUMMARY: "summary",
            RunPhase.EXTRAPOLATION: "extrapolation",
            RunPhase.FINISHED: END,
        },
    )

    workflow.add_edge("extrapolation", "manager")

    return workflow.compile()


app_graph = create_workflow()

