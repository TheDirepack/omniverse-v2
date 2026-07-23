from app.core.domain import RESEARCH_SCHEMA
from .common import C_STAGING_DB, OUTPUT_MODES_BLOCK, ITERATIVE_RESEARCH_PHILOSOPHY


def get_researcher_prompt(
    entity: str,
    requirements: str,
    focus: str | None = None,
    previous_dataset: str | None = None,
    outstanding_corrections: str | None = None,
    verified_claims: str | None = None,
    knowledge_graph: str | None = None,
    multiverse_leads: str | None = None,
    multiverse_kg: str | None = None,
    workspace_index: str | None = None,
    notebook_index: str | None = None,
    source_index: str | None = None,
    timeline_index: str | None = None,
):
    focus_block = ""
    if focus:
        focus_block = f"""FOCUSED FEATURE TARGET
Investigate this feature specifically: {focus}
Goal: prove existence, disprove existence, or mark inconclusive. Extract details, mechanism, limits, contradictions, and citations.
Add an item named "Focused Verdict" with Detail containing one of: VERIFIED, DISPROVED, INCONCLUSIVE."""

    verified_block = ""
    if verified_claims and verified_claims.strip():
        verified_block = f"""VERIFIED KNOWLEDGE BASE:
The following facts are already confirmed in the main database. Use them as anchors for expanding the investigation; do not spend time rediscovering them unless new evidence directly contradicts them.
{verified_claims}"""

    graph_block = ""
    if knowledge_graph and knowledge_graph.strip():
        graph_block = f"""EXISTING KNOWLEDGE GRAPH (FRONTIER USAGE):
Current semantic mapping of the universe:
{knowledge_graph}

INSTRUCTION: Treat the Knowledge Graph as your frontier. Identify unexplored nodes, disconnected subgraphs, and hanging relations. Your research actions must actively expand the frontier by exploring unmapped entities and resolving dangling references."""

    multiverse_block = ""
    if multiverse_leads or multiverse_kg:
        leads = multiverse_leads or "None"
        kg = multiverse_kg or "None"
        multiverse_block = f"""MULTIVERSE LEADS (Parent/Children Universes):
The following data exists for related universes in the multiverse:
LEADS:
{leads}

KNOWLEDGE GRAPH:
{kg}

IMPORTANT: This data is NOT necessarily true for the current universe/timeline. Use it to identify what to check and where gaps might be, but you MUST independently verify every lead and explicitly document any deviations."""

    workspace_block = ""
    if workspace_index or notebook_index or source_index or timeline_index:
        if workspace_index:
            workspace_block = f"""RESEARCH WORKSPACE (Strict Living Notebook Contract)
{workspace_index}

STRICT LIVING NOTEBOOK CONTRACT:
- The notebook is a live operational scratchpad, NOT a static task list.
- You MUST update, resolve, invalidate, or spawn notebook entries during every iteration using `loadNotebookEntry`.
- Never treat notebook items as completed checklists to ignore; treat them as active hypotheses subject to continuous falsification or refinement."""
        else:
            n_idx = notebook_index or "No active notes."
            s_idx = source_index or "No curated sources."
            t_idx = timeline_index or "No timeline events recorded."
            workspace_block = f"""RESEARCH WORKSPACE (Strict Living Notebook Contract)
The following indices represent your persistent research state. Use `loadNotebookEntry`, `manageSource`, and `recordTimelineEvent` to interact with them.

NOTEBOOK INDEX (Active Leads & Hypotheses):
{n_idx}

SOURCE LIBRARY INDEX (Evidence Base - Source Hierarchy):
{s_idx}

TIMELINE INDEX (Chronology):
{t_idx}

STRICT LIVING NOTEBOOK CONTRACT:
- The notebook is a live operational scratchpad, NOT a static task list.
- You MUST update, resolve, invalidate, or spawn notebook entries during every iteration using `loadNotebookEntry`.
- Never treat notebook items as completed checklists to ignore; treat them as active hypotheses subject to continuous falsification or refinement.
- SOURCE HIERARCHY: Prioritize primary canon text over secondary compilations, developer commentary, or derivative lore summaries when evaluating evidence."""

    mode_block = "INITIAL RESEARCH"
    if previous_dataset:
        mode_block = f"""PATCH & REFINE MODE
        You are updating an existing dataset.
        PREVIOUS DATASET:
        {previous_dataset}

        OUTSTANDING CORRECTIONS:
        {outstanding_corrections or "None"}

        INSTRUCTIONS:
        1. ABSOLUTE PRIORITY: Outstanding Corrections take precedence over all other leads. Resolve them first before proceeding to new research.
        2. TARGETED FIXES: Identify exactly which entries are affected by the Outstanding Corrections and fix them.
        3. STABILITY: Keep all unaffected verified data exactly as it is.
        4. PATCHING: Update the JSON by patching only the necessary fields."""

        system_parts = [
            f"### ROLE\nProfessional Lore Archivist & Technical Documentation Specialist for {entity}. Your mission is to produce the most complete, accurate, and well-supported record of the assigned world that can be constructed from available evidence.",
            f"MODE: {mode_block}",
            verified_block,
            graph_block,
            multiverse_block,
            workspace_block,
            OUTPUT_MODES_BLOCK,
            ITERATIVE_RESEARCH_PHILOSOPHY,
            """CORE DIRECTIVES
            - NO HEADCANON: Do not invent missing lore or reconcile contradictions through speculation. When evidence is incomplete or conflicting, document the uncertainty in the notebook and continue gathering evidence.
            - TECHNICAL RIGOR: Explicitly avoid general descriptive summaries (e.g., 'highly powerful'); instead, extract the specific evidence, exact parameters, operational mechanisms, and strict boundary conditions.
            - PRECISE GROUNDING: Every claim MUST have a Reference as 'url: section/L#'.
            - NO EXTERNAL KNOWLEDGE: If evidence is missing from source text, mark it in `Missing_Info`.
            - NOVELTY & INFO GAIN: Proactively identify coverage gaps (e.g., missing years in a timeline). Prefer actions with maximum expected information gain.
            - STOPPING HEURISTIC: Stop only when additional research has low expected information gain, not just because the notebook is exhausted.
            - NO THEORY: Do not construct high-level explanatory theories or causal mechanisms unless directly supported by evidence. Leave interpretation to downstream Theory Agents.""",
            C_STAGING_DB,
            focus_block,
            f"SCHEMA OUTPUT REQUIREMENTS\nYour final response JSON must strictly adhere to the schema below, ensuring all required fields, nested objects, and types are correct:\n{RESEARCH_SCHEMA}",
        ]
        return {
            "system": "\n\n".join([p for p in system_parts if p.strip()]),
            "user": f"Perform the research operation for {entity}. Follow the iterative research methodology until sufficient information is verified.",
        }

    # Initial research mode (no previous dataset)
    system_parts = [
        f"### ROLE\nProfessional Lore Archivist & Technical Documentation Specialist for {entity}. Your mission is to produce the most complete, accurate, and well-supported record of the assigned world that can be constructed from available evidence.",
        f"MODE: {mode_block}",
        verified_block,
        graph_block,
        multiverse_block,
        workspace_block,
        OUTPUT_MODES_BLOCK,
        ITERATIVE_RESEARCH_PHILOSOPHY,
        """CORE DIRECTIVES
        - NO HEADCANON: Do not invent missing lore or reconcile contradictions through speculation. When evidence is incomplete or conflicting, document the uncertainty in the notebook and continue gathering evidence.
        - TECHNICAL RIGOR: Explicitly avoid general descriptive summaries (e.g., 'highly powerful'); instead, extract the specific evidence, exact parameters, operational mechanisms, and strict boundary conditions.
        - PRECISE GROUNDING: Every claim MUST have a Reference as 'url: section/L#'.
        - NO EXTERNAL KNOWLEDGE: If evidence is missing from source text, mark it in `Missing_Info`.
        - NOVELTY & INFO GAIN: Proactively identify coverage gaps (e.g., missing years in a timeline). Prefer actions with maximum expected information gain.
        - STOPPING HEURISTIC: Stop only when additional research has low expected information gain, not just because the notebook is exhausted.
        - NO THEORY: Do not construct high-level explanatory theories or causal mechanisms unless directly supported by evidence. Leave interpretation to downstream Theory Agents.""",
        C_STAGING_DB,
        focus_block,
        f"SCHEMA OUTPUT REQUIREMENTS\nYour final response JSON must strictly adhere to the schema below, ensuring all required fields, nested objects, and types are correct:\n{RESEARCH_SCHEMA}",
        f"CONSTRAINTS\n- No markdown formatting, no code fences (no ```), no commentary.\n- Single parseable JSON object.\n- No invented data.\n- PROHIBITED: No power-scaling, feat analysis, or relative strength comparisons.\nRequirements: {requirements}"
    ]
    return {
        "system": "\n\n".join([p for p in system_parts if p.strip()]),
        "user": f"Perform the research operation for {entity}. Follow the iterative research methodology until sufficient information is verified.",
    }
