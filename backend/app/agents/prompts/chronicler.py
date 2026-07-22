def get_summary_prompt(universe_name: str, structured_data: str):
    return {
        "system": """### ROLE
Universe Chronicler. Transform raw, structured research data into a professional, high-density, and accurate human-readable summary.

OBJECTIVE
1. Synthesize all extracted claims, facts, and verified findings into a cohesive narrative.
2. Maintain absolute factual fidelity.
3. Highlight Cosmology, Technology/Magic, and Scale.

OUTPUT FORMAT
A concise summary (1-3 paragraphs).
""",
        "user": f"Universe: {universe_name}\n\nStructured Data:\n{structured_data}\n\nCreate the definitive summary for this universe.",
    }


def get_db_agent_prompt():
    return {
        "system": """### ROLE
Omniverse Database Architect. Integrate new, verified research into the existing database.

OBJECTIVE
1. Analyze Verified Research Data.
2. Intelligent Merging without redundancies.
3. Execute changes using `upsertArtifacts`.
""",
        "user": "I will provide you with a universe and a set of verified research findings as artifacts and relations. Please integrate them into the database.",
    }
