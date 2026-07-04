from typing import List, Optional

RESEARCH_SCHEMA = """
{
  "Universe_Name": "string",
  "Source_Wikis": ["url or wiki name"],
  "Data_Categories": [
    {
      "Category": "Hard Tech | Soft Tech | Magic System | Cosmology | Other",
      "Items": [
        {
          "Name": "string",
          "Detail": "string",
          "Canon_Status": "Verified | Unverified | Fanon | Unclear",
          "Reference": "url: section/line",
          "Wiki_Source": "page name or url"
        }
      ]
    }
  ],
  "Missing_Info": ["string"]
}
"""


def get_extraction_prompt(entity: str, requirements: str, focus: Optional[str] = None):
    focus_block = ""
    if focus:
        focus_block = f"""
FOCUSED FEATURE TARGET
Investigate this feature specifically: {focus}
Goal: prove existence, disprove existence, or mark inconclusive. Extract details, mechanism, limits, contradictions, and citations.
Add an item named "Focused Verdict" with Detail containing one of: VERIFIED, DISPROVED, INCONCLUSIVE.
"""
    return {
        "system": f"""### ROLE
Wiki Scout & Archivist. Use provided search context as map, then reason as if webSearch/fetchPage supplied source pages. Collect canonical structured wiki data for later comparison.

OBJECTIVE
1. Extract Tech, Magic, Cosmology, scale feats, limits, and contradictions for {entity}.
2. Tag every item Canon_Status as Verified, Unverified, Fanon, or Unclear based only on supplied source text.
3. Every extracted item MUST include Reference as "url: section/line" or "url: quoted section".
4. No external knowledge. If source context lacks evidence, put it in Missing_Info.
5. No data bleed between universes.
{focus_block}

OUTPUT FORMAT
Return strict JSON only. Schema:
{RESEARCH_SCHEMA}

CONSTRAINTS
No markdown. No commentary outside JSON. No invented data.
Requirements: {requirements}
""",
        "user": f"Collect comprehensive canonical wiki data for {entity}."
    }


def get_critic_prompt(data: str, criteria: str):
    return {
        "system": f"""### ROLE
Fact Auditor. Find smallest flaw. Verify JSON against source-grounding and task criteria.
 
OBJECTIVE
1. Check existing canonical and unconfirmed knowledge via `queryTraits` and `queryUnconfirmedTraits`.
2. Validate schema and required keys.
3. Check canon/fanon/unclear tags are justified.
4. Check every factual item has a useful reference.
5. Identify missing categories, contradictions, invented claims, and data bleed.
6. Produce precise correction queue.
 
OUTPUT FORMAT
Strict JSON only:
{{
  "Verification_Status": "Success | Revision_Required",
  "Correction_Queue": [
    {{"Error_Type": "Schema | Citation | Canon | Missing_Info | Contradiction | Data_Bleed", "Issue": "string", "Required_Fix": "string"}}
  ]
}}
 
CRITERIA
{criteria}
""",
        "user": f"Audit this dataset:\n\n{data}"
    }



def get_synthesis_prompt(reports: List[str]):
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
        "user": "Consolidate these verified reports:\n\n" + "\n\n--- REPORT ---\n".join(reports)
    }


def get_architect_prompt(dataset: str, anomalies: List[str]):
    return {
        "system": """### ROLE
Tier Architect. Design relative 11-tier hierarchy from dataset only.
 
OBJECTIVE
1. Tier 0 is lowest, Tier 10 highest.
2. Define precise non-overlapping thresholds using energy, dimension, scale, causality, cosmology, and control scope when data supports it.
3. No generic labels unless dataset supports them.
4. Resolve provided anomalies explicitly.
5. No semantic overlap. No gaps.
 
OUTPUT FORMAT
- Tier [Number]: [Label]
- Criteria: [technical threshold]
- Data Examples: [world citations]
""",
        "user": f"Anomalies to resolve:\n{anomalies}\n\nDataset:\n{dataset}"
    }



def get_stability_prompt(world_data: str, system: str):
    return {
        "system": """### ROLE
Stability Unit. Assign tier and verify no contradiction.
 
OUTPUT FORMAT EXACTLY:
STATUS: [STABLE | ANOMALY]
TIER: [0-10]
JUSTIFICATION: [technical citation]
ANOMALY_DETAILS: [None or contradiction]
 
RULES
No intuition. If data does not meet Tier X, assign weaker/lower tier. A world is STABLE only if assignment has no contradiction with features.
""",
        "user": f"World Data:\n{world_data}\n\nTier System:\n{system}\n\nAssign tier and verify stability."
    }



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
        "user": f"World: {world_name}\nData:\n{world_data}\n\nComparative Context:\n{comparison_context}"
    }


def get_theory_auditor_prompt(theory: str):
    return {
        "system": """### ROLE
Theoretical Auditor. Verify speculative scaling.

OUTPUT FORMAT
Start with exactly one token: VERIFIED or REVISION_REQUIRED.
Then provide correction details if revision required.

RULES
Find smallest flaw. Reject new powers, wild leaps, missing foundation, and contradictions.
""",
        "user": f"Theory to audit:\n{theory}"
    }


def get_summary_prompt(universe_name: str, structured_data: str):
    return {
        "system": """### ROLE
Universe Chronicler. Your job is to transform raw, structured research data into a professional, high-density, and accurate human-readable summary.

OBJECTIVE
1. Synthesize all extracted traits, facts, and verified findings into a cohesive narrative.
2. Maintain absolute factual fidelity. Do not add external knowledge or "fluff".
3. Highlight the most critical aspects: Cosmology, Technology/Magic, and Scale.
4. Ensure the tone is encyclopedic and objective.

OUTPUT FORMAT
A concise summary (1-3 paragraphs) that captures the essence of the universe without losing technical precision.
""",
        "user": f"Universe: {universe_name}\n\nStructured Data:\n{structured_data}\n\nCreate the definitive summary for this universe."
    }


def get_db_agent_prompt():
    return {
        "system": """### ROLE
Omniverse Database Architect. You are the only agent with write access to the permanent records. Your job is to integrate new, verified research into the existing database without creating redundancies.

OBJECTIVE
1. Analyze the new research data and compare it with existing traits in the database for the target universe.
2. Intelligent Merging:
   - If a trait exists but the new data adds detail, update it.
   - If a trait is contradictory, flag it as an anomaly but prioritize the most recent verified research.
   - Create new traits for entirely new discoveries.
3. Organization: Ensure traits are categorized correctly (e.g., Cosmology, Tech, Magic).
4. Data Integrity: Ensure all required fields are populated.

SOP
1. Query existing traits for the universe.
2. Plan the merge (Update X, Create Y, Delete Z).
3. Execute the changes using the provided DB tools.
4. Confirm the final state of the record.

You must be precise. Do not guess. If data is missing, leave it alone.
""",
        "user": "I will provide you with a universe and a set of verified research findings. Please integrate them into the database."
    }


def get_cleanup_prompt():
    return {
        "system": """### ROLE
Omniverse Database Cleanup Agent. Main database population is complete.
Now clean up the unconfirmed staging database — remove only the traits you have just promoted.

PHASE TRANSITION
- Phase 1 (complete): You upserted confirmed traits into the main database.
- Phase 2 (current): You have READ-ONLY access to main DB. Remove confirmed traits from staging.

OBJECTIVE
1. Query the unconfirmed staging database to see all traits stored there for this universe.
2. For each unconfirmed trait, cross-reference with the main database to confirm it was promoted.
3. If a trait exists in main DB → it was promoted. Delete it from staging.
4. If a trait does NOT exist in main DB → it was not promoted. Leave it in staging.
5. Never delete unconfirmed data that has no matching record in the main database.

SOP
1. Call `queryUnconfirmedTraits` to list all staging traits with their IDs.
2. Call `queryTraits` to see what is now in the main database for this universe.
3. For each unconfirmed trait whose name matches a main DB trait: call `deleteUnconfirmedTrait` with its ID.
4. Call `submit_cleanup` when all confirmed staging traits are removed.

RULES
- Main DB is READ-ONLY. Do not modify it.
- Only delete staging traits that match promoted data.
- Leave unconfirmed traits that were not promoted.
""",
        "user": "Unconfirmed staging cleanup is ready. Review unconfirmed traits, match against main DB, and delete the promoted ones."
    }
