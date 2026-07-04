from langgraph.graph import StateGraph, END
from app.agents.state import OmniverseState
from app.agents.nodes import (
    research_node,
    manager_node,
    extrapolation_node,
    summary_node,
    db_integrator_node
)



def create_workflow():
    workflow = StateGraph(OmniverseState)

    # Add Nodes
    workflow.add_node("research", research_node)
    workflow.add_node("db_integrator", db_integrator_node)
    workflow.add_node("summary", summary_node)
    workflow.add_node("manager", manager_node)
    workflow.add_node("extrapolation", extrapolation_node)


    # Set Entry Point
    workflow.set_entry_point("research")

    # Define Edges
    workflow.add_edge("research", "db_integrator")
    workflow.add_edge("db_integrator", "summary")
    workflow.add_edge("summary", END)
    
    # Conditional Routing from Manager
    workflow.add_conditional_edges(
        "manager",
        lambda state: state["active_task"],
        {
            "RESEARCH": "research",
            "DB_INTEGRATION": "db_integrator",
            "SUMMARY": "summary",
            "EXTRAPOLATION": "extrapolation",
            "FINISHED": END
        }
    )


    workflow.add_edge("extrapolation", "manager")

    return workflow.compile()

app_graph = create_workflow()
