from app.agents.workflow import app_graph, create_workflow


class TestWorkflowCreation:
    def test_create_workflow(self):
        graph = create_workflow()
        assert graph is not None

    def test_app_graph_is_compiled(self):
        assert app_graph is not None

    def test_graph_has_expected_nodes(self):
        graph = create_workflow()
        assert hasattr(graph, "get_graph")
        g = graph.get_graph()
        assert "research" in g.nodes
        assert "manager" in g.nodes
        assert "db_integrator" in g.nodes
        assert "summary" in g.nodes
        assert "extrapolation" in g.nodes
        assert "consolidation" not in g.nodes
