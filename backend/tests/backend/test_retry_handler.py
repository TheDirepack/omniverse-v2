import json

from app.core.retry_handler import RetryHandler


class TestRetryHandlerInit:
    def test_default_max_iterations(self):
        rh = RetryHandler()
        assert rh.max_iterations == 3
        assert rh.current_iteration == 0
        assert rh.last_result is None
        assert rh.feedback_history == []
        assert rh.agent_history is None

    def test_custom_max_iterations(self):
        rh = RetryHandler(max_iterations=5)
        assert rh.max_iterations == 5


class TestRetryHandlerUpdateState:
    def test_update_with_valid_json_critique(self):
        rh = RetryHandler()
        critique = json.dumps({"Correction_Queue": [{"Issue": "Fix this"}]})
        rh.update_state("result1", critique, "history")
        assert rh.current_iteration == 1
        assert rh.last_result == "result1"
        assert rh.agent_history == "history"
        assert len(rh.feedback_history) == 1
        assert rh.feedback_history[0]["corrections"] == [{"Issue": "Fix this"}]
        assert rh.feedback_history[0]["status"] == "OUTSTANDING"

    def test_update_with_no_corrections(self):
        rh = RetryHandler()
        critique = json.dumps({"Correction_Queue": []})
        rh.update_state("result", critique, None)
        assert rh.feedback_history[0]["corrections"] == []

    def test_update_with_invalid_json_critique(self):
        rh = RetryHandler()
        rh.update_state("result", "not valid json", "hist")
        assert len(rh.feedback_history) == 1
        assert rh.feedback_history[0]["corrections"][0]["Issue"] == "not valid json"

    def test_update_with_type_error_critique(self):
        rh = RetryHandler()
        rh.update_state("result", None, "hist")
        assert len(rh.feedback_history) == 1
        assert "General revision required" in (
            rh.feedback_history[0]["corrections"][0]["Required_Fix"]
        )

    def test_multiple_updates_accumulate(self):
        rh = RetryHandler()
        rh.update_state("r1", json.dumps({"Correction_Queue": [{"Issue": "A"}]}), "h1")
        rh.update_state("r2", json.dumps({"Correction_Queue": [{"Issue": "B"}]}), "h2")
        assert rh.current_iteration == 2
        assert len(rh.feedback_history) == 2
        assert rh.feedback_history[0]["corrections"][0]["Issue"] == "A"
        assert rh.feedback_history[1]["corrections"][0]["Issue"] == "B"


class TestRetryHandlerGetFeedbackSummary:
    def test_no_feedback_returns_none(self):
        rh = RetryHandler()
        assert rh.get_feedback_summary() == "None"

    def test_outstanding_only(self):
        rh = RetryHandler()
        rh.feedback_history = [
            {
                "attempt": 1,
                "corrections": [{"Issue": "Bad data", "Required_Fix": "fix it"}],
                "status": "OUTSTANDING",
            }
        ]
        summary = rh.get_feedback_summary()
        assert "OUTSTANDING:" in summary
        assert "Bad data" in summary
        assert "RESOLVED:" in summary

    def test_resolved_only(self):
        rh = RetryHandler()
        rh.feedback_history = [
            {
                "attempt": 1,
                "corrections": [{"Issue": "Fixed issue"}],
                "status": "RESOLVED",
            }
        ]
        summary = rh.get_feedback_summary()
        assert "✓ Fixed issue" in summary
        assert "RESOLVED:" in summary

    def test_mixed_resolved_and_outstanding(self):
        rh = RetryHandler()
        rh.feedback_history = [
            {
                "attempt": 1,
                "corrections": [{"Issue": "Done", "Required_Fix": "already"}],
                "status": "RESOLVED",
            },
            {
                "attempt": 1,
                "corrections": [{"Issue": "Pending", "Required_Fix": "needs work"}],
                "status": "OUTSTANDING",
            },
        ]
        summary = rh.get_feedback_summary()
        assert "✓ Done" in summary
        assert "Pending" in summary

    def test_fix_as_dict_formats_properly(self):
        rh = RetryHandler()
        fix_dict = {"action": "update", "target": "field", "reason": "incorrect"}
        rh.feedback_history = [
            {
                "attempt": 1,
                "corrections": [{"Issue": "Wrong value", "Required_Fix": fix_dict}],
                "status": "OUTSTANDING",
            }
        ]
        summary = rh.get_feedback_summary()
        assert "update field (incorrect)" in summary

    def test_fix_as_non_dict_string(self):
        rh = RetryHandler()
        rh.feedback_history = [
            {
                "attempt": 1,
                "corrections": [{"Issue": "Error", "Required_Fix": "just fix it"}],
                "status": "OUTSTANDING",
            }
        ]
        summary = rh.get_feedback_summary()
        assert "Fix: just fix it" in summary

    def test_multiple_corrections_in_one_entry(self):
        rh = RetryHandler()
        rh.feedback_history = [
            {
                "attempt": 1,
                "corrections": [
                    {"Issue": "A", "Required_Fix": "fix A"},
                    {"Issue": "B", "Required_Fix": "fix B"},
                ],
                "status": "OUTSTANDING",
            }
        ]
        summary = rh.get_feedback_summary()
        assert "A" in summary
        assert "B" in summary


class TestRetryHandlerGetResearchQueue:
    def test_no_last_result_returns_empty(self):
        rh = RetryHandler()
        assert rh.get_research_queue() == ""

    def test_valid_json_with_leads_and_missing(self):
        rh = RetryHandler()
        rh.last_result = json.dumps({
            "Knowledge_Graph": [{"Lead": "L1", "Expected_Value": "EV1"}],
            "Missing_Info": ["M1", "M2"],
        })
        queue = rh.get_research_queue()
        assert "PRIORITY LEADS:" in queue
        assert "- L1 (EV1)" in queue
        assert "UNRESOLVED GAPS:" in queue
        assert "- M1" in queue
        assert "- M2" in queue

    def test_valid_json_without_leads_or_missing(self):
        rh = RetryHandler()
        rh.last_result = json.dumps({
            "Knowledge_Graph": [],
            "Missing_Info": [],
        })
        assert rh.get_research_queue() == ""

    def test_invalid_json_returns_empty(self):
        rh = RetryHandler()
        rh.last_result = "not json"
        assert rh.get_research_queue() == ""

    def test_type_error_in_last_result_returns_empty(self):
        rh = RetryHandler()
        rh.last_result = None
        assert rh.get_research_queue() == ""

    def test_leads_without_expected_value(self):
        rh = RetryHandler()
        rh.last_result = json.dumps({
            "Knowledge_Graph": [{"Lead": "L1"}],
            "Missing_Info": ["M1"],
        })
        queue = rh.get_research_queue()
        assert "L1 (Unknown)" in queue


class TestRetryHandlerHandleFinalAttempt:
    def test_final_attempt_with_sifted_dataset_string(self):
        rh = RetryHandler()
        critique = json.dumps({"Sifted_Dataset": "final data"})
        assert rh.handle_final_attempt(critique) == "final data"

    def test_final_attempt_with_sifted_dataset_dict(self):
        rh = RetryHandler()
        critique = json.dumps({"Sifted_Dataset": {"key": "val"}})
        assert json.loads(rh.handle_final_attempt(critique)) == {"key": "val"}

    def test_no_sifted_dataset(self):
        rh = RetryHandler()
        critique = json.dumps({"other": "data"})
        assert rh.handle_final_attempt(critique) is None

    def test_invalid_json_returns_none(self):
        rh = RetryHandler()
        assert rh.handle_final_attempt("bad json") is None

    def test_type_error_returns_none(self):
        rh = RetryHandler()
        assert rh.handle_final_attempt(None) is None


class TestRetryHandlerIsFinalAttempt:
    def test_not_final_initial(self):
        rh = RetryHandler(max_iterations=3)
        assert not rh.is_final_attempt()

    def test_final_at_iteration_2(self):
        rh = RetryHandler(max_iterations=3)
        rh.current_iteration = 2
        assert rh.is_final_attempt()

    def test_final_not_reached_yet(self):
        rh = RetryHandler(max_iterations=3)
        rh.current_iteration = 1
        assert not rh.is_final_attempt()

    def test_custom_max_iterations(self):
        rh = RetryHandler(max_iterations=5)
        rh.current_iteration = 3
        assert not rh.is_final_attempt()
        rh.current_iteration = 4
        assert rh.is_final_attempt()


class TestRetryHandlerIterationCount:
    def test_initial_count(self):
        rh = RetryHandler()
        assert rh.iteration_count == 1

    def test_after_one_update(self):
        rh = RetryHandler()
        rh.current_iteration = 1
        assert rh.iteration_count == 2

    def test_after_multiple_updates(self):
        rh = RetryHandler()
        rh.current_iteration = 5
        assert rh.iteration_count == 6

    def test_update_state_resolves_previous_issues(self):
        rh = RetryHandler()
        # Turn 1: Issue A is outstanding
        rh.update_state("r1", json.dumps({"Correction_Queue": [{"Issue": "Issue A"}]}), "h1")
        assert rh.feedback_history[0]["corrections"][0]["status"] == "OUTSTANDING"

        # Turn 2: Issue A is gone, Issue B is now outstanding
        rh.update_state("r2", json.dumps({"Correction_Queue": [{"Issue": "Issue B"}]}), "h2")

        # Issue A should be RESOLVED
        assert rh.feedback_history[0]["corrections"][0]["status"] == "RESOLVED"
        # Issue B should be OUTSTANDING
        assert rh.feedback_history[1]["corrections"][0]["status"] == "OUTSTANDING"
