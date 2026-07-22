def get_extrapolation_prompt(world_name: str, world_data: str, comparison_context: str):
    return {
        "system": """### ROLE
Ontological Theorist. Extrapolate hypothetical interactions/scaling from canon data plus comparative context.

OBJECTIVE
1. Scaling Projections: relative interaction scale.
2. Peak Extrapolations: logical maximums from known mechanics.
3. Vulnerability Analysis: weaknesses/blind spots.
4. No new powers. Only extend documented logic conservatively.

OUTPUT FORMAT
Report with sections: Scaling Projections, Peak Extrapolations, Vulnerability Analysis, Foundations.
""",
        "user": f"World: {world_name}\nData:\n{world_data}\n\nComparative Context:\n{comparison_context}",
    }


def get_theory_auditor_prompt(theory: str):
    return {
        "system": """### ROLE
Theoretical Auditor. Verify speculative scaling.

OUTPUT FORMAT
Start with exactly one token: VERIFIED or REVISION_REQUIRED.
Then provide correction details if revision required.
""",
        "user": f"Theory to audit:\n{theory}",
    }
