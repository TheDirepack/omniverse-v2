def get_synthesis_prompt(reports: list[str]):
    return {
        "system": """### ROLE
Consolidator. Merge verified reports into a master dataset.

OBJECTIVE
1. Preserve universe separation. No data bleed.
2. Dedupe repeated items while preserving strongest citation.
3. Maintain compact high-density technical summaries.
4. Keep canon/fanon/unclear distinctions.

OUTPUT FORMAT
Structured markdown or JSON is acceptable, but each world must remain separately labeled.
""",
        "user": "Consolidate these verified reports:\n\n"
        + "\n\n--- REPORT ---\n".join(reports),
    }
