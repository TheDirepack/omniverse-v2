from unittest.mock import AsyncMock, MagicMock, patch

from app.research.summarizer import summarize_universe


class TestSummarizer:
    @patch("app.research.summarizer.UniverseService")
    @patch("app.research.summarizer.run_agent", new_callable=AsyncMock)
    @patch("app.research.summarizer.set_current_universe")
    async def test_summarize_success(
        self, mock_set_ctx, mock_run_agent, mock_uni_service
    ):
        uni = MagicMock()
        uni.name = "TestUniverse"
        mock_service = MagicMock()
        mock_service.get_universe_by_id.return_value = uni
        mock_service.get_verified_claims.return_value = [
            MagicMock(
                subject_id=1, predicate="IS", object_literal="strong",
                object_entity_id=None
            ),
            MagicMock(
                subject_id=2, predicate="HAS", object_literal=None,
                object_entity_id=3
            ),
        ]
        mock_uni_service.return_value = mock_service
        mock_run_agent.return_value = ("Test summary", None)

        result = await summarize_universe(universe_id=1, run_id="run-1")

        assert result == "Test summary"
        mock_set_ctx.assert_called_once_with("TestUniverse")
        mock_run_agent.assert_called_once()
        mock_service.update_summary.assert_called_once_with(1, "Test summary")

    @patch("app.research.summarizer.UniverseService")
    @patch("app.research.summarizer.run_agent", new_callable=AsyncMock)
    async def test_summarize_universe_not_found(self, mock_run_agent, mock_uni_service):
        mock_service = MagicMock()
        mock_service.get_universe_by_id.return_value = None
        mock_uni_service.return_value = mock_service

        result = await summarize_universe(universe_id=99, run_id="run-2")

        assert result == "Universe not found."
        mock_run_agent.assert_not_called()

    @patch("app.research.summarizer.UniverseService")
    @patch("app.research.summarizer.run_agent", new_callable=AsyncMock)
    @patch("app.research.summarizer.set_current_universe")
    async def test_summarize_no_claims(
        self, mock_set_ctx, mock_run_agent, mock_uni_service
    ):
        uni = MagicMock()
        uni.name = "EmptyUniverse"
        mock_service = MagicMock()
        mock_service.get_universe_by_id.return_value = uni
        mock_service.get_verified_claims.return_value = []
        mock_uni_service.return_value = mock_service
        mock_run_agent.return_value = ("Empty summary", None)

        result = await summarize_universe(universe_id=2, run_id="run-3")

        assert result == "Empty summary"
        mock_set_ctx.assert_called_once_with("EmptyUniverse")
        assert any(
            "No verified claims" in str(v)
            for v in mock_run_agent.call_args.kwargs.values()
        )
