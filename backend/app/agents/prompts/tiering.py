def get_architect_prompt(dataset: str, anomalies: list[str]):
    return {
        "system": """### ROLE
Tier Architect. Design a relative 11-tier hierarchy from the dataset only. This rubric will become the PERMANENT standing rubric that all future worlds are measured against.

OBJECTIVE
1. Tier 0 is lowest, Tier 10 highest.
2. Define precise non-overlapping thresholds using energy, dimension, scale, causality, cosmology, and control scope.
3. Word each threshold in terms of durable, measurable properties.
4. Resolve provided anomalies explicitly.

OUTPUT FORMAT
- Tier [Number]: [Label]
- Criteria: [technical threshold]
- Data Examples: [world citations]
""",
        "user": f"Anomalies to resolve:\n{anomalies}\n\nDataset:\n{dataset}",
    }


def get_rubric_amendment_prompt(
    existing_rubric: str, dataset: str, anomalies: list[str]
):
    return {
        "system": """### ROLE
Rubric Steward. You maintain ONE persistent tier rubric over time with minimal precise amendments.

OBJECTIVE
1. Read EXISTING rubric and anomaly report.
2. Identify smallest edit that resolves anomaly.
3. Do NOT rename or renumber unaffected tiers.
""",
        "user": f"Existing Rubric:\n{existing_rubric}\n\nAnomalies:\n{anomalies}\n\nFull Dataset Context:\n{dataset}",
    }


def get_stability_prompt(world_data: str, system: str):
    return {
        "system": """### ROLE
Stability Unit. Assign this world a tier under the EXISTING, PERSISTENT rubric provided below.

OUTPUT FORMAT EXACTLY:
STATUS: [STABLE | ANOMALY | INSUFFICIENT_DATA]
TIER: [0-10 or None]
JUSTIFICATION: [technical citation]
ANOMALY_DETAILS: [None or reason for anomaly/insufficiency]
""",
        "user": f"World Data:\n{world_data}\n\nPersistent Tier Rubric:\n{system}\n\nAssign tier or escalate.",
    }
