from typing import Any

from sqlmodel import Session, select

from app.db.schema import Claim, Entity, EntityAlias
from app.db.session import engine


class KnowledgeRetrieverService:
    def __init__(self, session: Session | None = None):
        self.session = session

    def get_universe_knowledge_graph(self, universe_id: int) -> dict[str, Any]:
        """
        Transforms raw relational claims into a semantic graph for LLM consumption.
        Returns a mapping of Entity Name -> {facts: [], related: []}.
        """
        session = self.session or Session(engine)
        try:
            # 1. Get all entities and their aliases for this universe
            entities = session.exec(
                select(Entity).where(Entity.universe_id == universe_id)
            ).all()
            aliases = session.exec(
                select(EntityAlias).where(EntityAlias.universe_id == universe_id)
            ).all()

            id_to_name = {}
            name_to_id = {}

            for e in entities:
                id_to_name[e.id] = e.name
                name_to_id[e.name] = e.id

            # Map aliases back to canonical names
            alias_map = {}
            for a in aliases:
                canonical_name = id_to_name.get(a.entity_id, "Unknown")
                alias_map[a.alias] = canonical_name

            # 2. Get all claims for this universe
            claims = session.exec(
                select(Claim).where(Claim.universe_scope == universe_id)
            ).all()

            # 3. Build the graph
            graph = {}

            for c in claims:
                # Resolve subject
                subj_name = id_to_name.get(c.subject_id, "Unknown")

                if subj_name not in graph:
                    graph[subj_name] = {
                        "entity": subj_name,
                        "facts": [],
                        "related_entities": set(),
                    }

                # Resolve object
                obj_val = c.object_literal
                if c.object_entity_id:
                    obj_val = id_to_name.get(
                        c.object_entity_id, f"Entity({c.object_entity_id})"
                    )

                # Add fact
                graph[subj_name]["facts"].append(
                    {
                        "predicate": c.predicate,
                        "object": obj_val,
                        "support": c.support_count,
                        "status": c.status,
                        "reference": c.source_reference,
                    }
                )

                # Add to related entities if object is an entity
                if c.object_entity_id:
                    graph[subj_name]["related_entities"].add(obj_val)

            # Convert sets to lists for JSON serialization
            for entity in graph.values():
                entity["related_entities"] = list(entity["related_entities"])

            return graph
        finally:
            if not self.session:
                session.close()

    def get_semantic_claims(
        self, universe_id: int, predicate_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Returns a flattened list of semantic claims, filtering if requested.
        """
        graph = self.get_universe_knowledge_graph(universe_id)
        semantic_list = []

        for entity_name, data in graph.items():
            for fact in data["facts"]:
                if predicate_filter and fact["predicate"] != predicate_filter:
                    continue

                semantic_list.append(
                    {
                        "subject": entity_name,
                        "predicate": fact["predicate"],
                        "object": fact["object"],
                        "support": fact["support"],
                        "reference": fact["reference"],
                    }
                )

        return semantic_list

    def get_claims_dataset(self, universe_id: int) -> str:
        """
        Returns a formatted dataset string of all verified claims for a universe.
        Used for Tiering and Extrapolation to ensure structured data input.
        """
        claims = self.get_semantic_claims(universe_id)
        if not claims:
            return "No verified claims available."
        
        lines = [
            f"({c['subject']} --{c['predicate']}--> {c['object']}) [Support: {c['support']}]"
            for c in claims
        ]
        return "\n".join(lines)
