import json
from typing import List, Dict, Any, Optional

class RetryHandler:
    """
    Manages the state of the 'Patch & Refine' loop for research and auditing.
    Encapsulates history, queues, and results to move state out of procedural functions.
    """
    def __init__(self, max_iterations: int = 3):
        self.max_iterations = max_iterations
        self.current_iteration = 0
        self.last_result: Optional[str] = None
        self.feedback_history: List[Dict[str, Any]] = []
        self.agent_history: Any = None

    def update_state(self, result: str, critique: str, turn_history: Any):
        """
        Updates the internal state with the latest agent results and audit.
        """
        self.current_iteration += 1
        self.last_result = result
        self.agent_history = turn_history

        try:
            parsed_critique = json.loads(critique)
            corrections = parsed_critique.get("Correction_Queue", [])
            status = "OUTSTANDING"
            # Note: The actual 'SUCCESS' check is done via audit_success validator, 
            # but we track the raw corrections here.
            self.feedback_history.append({
                "attempt": self.current_iteration,
                "corrections": corrections,
                "status": status
            })
        except (json.JSONDecodeError, TypeError):
            self.feedback_history.append({
                "attempt": self.current_iteration,
                "corrections": [{"Issue": critique, "Required_Fix": "General revision required"}],
                "status": "OUTSTANDING"
            })

    def get_feedback_summary(self) -> str:
        """
        Generates the formatted summary of resolved and outstanding corrections for the prompt.
        """
        resolved = []
        outstanding = []
        for entry in self.feedback_history:
            for corr in entry["corrections"]:
                if entry["status"] == "RESOLVED":
                    resolved.append(f"✓ {corr['Issue']}")
                else:
                    fix = corr['Required_Fix']
                    fix_str = f"{fix['action']} {fix['target']} ({fix['reason']})" if isinstance(fix, dict) else str(fix)
                    outstanding.append(f"• {corr['Issue']} -> Fix: {fix_str}")
        
        if not resolved and not outstanding:
            return "None"
        
        return "\n".join([
            "RESOLVED:", *resolved, 
            "\nOUTSTANDING:", *outstanding
        ])

    def get_research_queue(self) -> str:
        """
        Extracts leads and gaps from the last result to prioritize in the next turn.
        """
        if not self.last_result:
            return ""
        
        try:
            data = json.loads(self.last_result)
            leads = [f"- {l['Lead']} ({l.get('Expected_Value', 'Unknown')})" for l in data.get("Knowledge_Graph", [])]
            missing = [f"- {m}" for m in data.get("Missing_Info", [])]
            if leads or missing:
                return "\n".join(["PRIORITY LEADS:"] + leads + ["\nUNRESOLVED GAPS:"] + missing)
        except (json.JSONDecodeError, TypeError, KeyError):
            pass
        
        return ""

    def handle_final_attempt(self, critique: str) -> Optional[str]:
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
