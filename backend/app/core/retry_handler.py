import json
from typing import Any


class RetryHandler:
    """
    Manages the state of the 'Patch & Refine' loop for research and auditing.
    Encapsulates history, queues, and results to move state out of procedural functions.
    """

    def __init__(self, max_iterations: int = 3):
        self.max_iterations = max_iterations
        self.current_iteration = 0
        self.last_result: str | None = None
        self.feedback_history: list[dict[str, Any]] = []
        self.agent_history: Any = None

    def update_state(self, result: str, critique: str, turn_history: Any):
        """
        Updates the internal state with the latest agent results and audit.
        Detects resolved corrections by comparing current issues with history.
        """
        self.current_iteration += 1
        self.last_result = result
        self.agent_history = turn_history

        try:
            parsed_critique = json.loads(critique)
            current_corrections = parsed_critique.get("Correction_Queue", [])

            # Mark previous corrections as resolved if they are no longer in the current queue
            current_issues = {c.get("Issue") for c in current_corrections if isinstance(c, dict)}
            for entry in self.feedback_history:
                for corr in entry.get("corrections", []):
                    if isinstance(corr, dict) and corr.get("status") != "RESOLVED":
                        if corr.get("Issue") not in current_issues:
                            corr["status"] = "RESOLVED"

            self.feedback_history.append(
                {
                    "attempt": self.current_iteration,
                    "corrections": [
                        {**c, "status": "OUTSTANDING"} if isinstance(c, dict) else {"Issue": c, "status": "OUTSTANDING"}
                        for c in current_corrections
                    ],
                }
            )
        except (json.JSONDecodeError, TypeError):
            self.feedback_history.append(
                {
                    "attempt": self.current_iteration,
                    "corrections": [
                        {"Issue": critique, "Required_Fix": "General revision required", "status": "OUTSTANDING"}
                    ],
                }
            )

    def get_feedback_summary(self) -> str:
        """
        Generates the formatted summary of resolved and outstanding corrections for the prompt.
        """
        resolved = []
        outstanding = []
        for entry in self.feedback_history:
            for corr in entry.get("corrections", []):
                if isinstance(corr, dict):
                    if corr.get("status") == "RESOLVED":
                        resolved.append(f"✓ {corr.get('Issue', 'Unknown')}")
                    elif corr.get("status") == "OUTSTANDING":
                        fix = corr.get("Required_Fix")
                        fix_str = (
                            f"{fix['action']} {fix['target']} ({fix['reason']})"
                            if isinstance(fix, dict)
                            else str(fix)
                        )
                        outstanding.append(f"• {corr.get('Issue', 'Unknown')} -> Fix: {fix_str}")
                else:
                    outstanding.append(f"• {corr} -> Fix: General revision")

        if not resolved and not outstanding:
            return "None"

        parts = []
        if resolved:
            parts.append("RESOLVED:\n" + "\n".join(resolved))
        if outstanding:
            parts.append("OUTSTANDING:\n" + "\n".join(outstanding))

        return "\n\n".join(parts)

    def get_research_queue(self) -> str:
        """
        Extracts leads and gaps from the last result to prioritize in the next turn.
        """
        if not self.last_result:
            return ""

        try:
            data = json.loads(self.last_result)
            leads = [
                f"- {lead['Lead']} ({lead.get('Expected_Value', 'Unknown')})"
                for lead in data.get("Knowledge_Graph", [])
            ]
            missing = [f"- {m}" for m in data.get("Missing_Info", [])]
            if leads or missing:
                return "\n".join(
                    ["PRIORITY LEADS:", *leads, "\nUNRESOLVED GAPS:", *missing]
                )
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

        return ""

    def handle_final_attempt(self, critique: str) -> str | None:
        """
        Extracts the Sifted_Dataset if it's the final attempt and the audit failed.
        """
        try:
            parsed_critique = json.loads(critique)
            if "Sifted_Dataset" in parsed_critique:
                sifted_data = parsed_critique["Sifted_Dataset"]
                if not isinstance(sifted_data, str):
                    return json.dumps(sifted_data)
                return sifted_data
        except (json.JSONDecodeError, TypeError):
            pass
        return None

    def is_final_attempt(self) -> bool:
        return self.current_iteration >= self.max_iterations - 1

    @property
    def iteration_count(self) -> int:
        return self.current_iteration + 1
