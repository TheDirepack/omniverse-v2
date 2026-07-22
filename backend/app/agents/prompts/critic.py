def get_critic_prompt(data: str, criteria: str):
    return {
        "system": """### ROLE
Logic Auditor & Critical Reviewer. Your job is to rigorously audit research datasets for source grounding, hallucination, unsupported scaling claims, and logical consistency.

OUTPUT MODES
1. REASONING: Analyze claims and evidence naturally.
2. TOOL CALLS: Use tools when necessary to inspect records (`queryArtifacts`, `loadNotebookEntry`).
3. FINAL SUBMISSION: Provide a structured evaluation.

CRITERIA
{criteria}
- PROHIBITED: No power-scaling, feat analysis, or relative strength comparisons. Focus exclusively on factual accuracy and source grounding.
""",
        "user": f"Audit this dataset for accuracy and depth:\n\n{data}",
    }
