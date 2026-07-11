import json
from typing import Any

from sqlmodel import Session, select

from app.db.schema import Artifact, ArtifactRelation
from app.db.session import engine


class KnowledgeRetrieverService:
    def __init__(self, session: Session | None = None):
        self.session = session

    def get_universe_knowledge_graph(self, universe_id: int) -> dict[str, Any]:
        """
        Transforms polymorphic Artifacts into a semantic graph for LLM consumption.
        Returns a mapping of Entity Name -> {facts: [], related: []}.
        """
        session = self.session or Session(engine)
        try:
            # 1. Get all entities for this universe
            entities = session.exec(
                select(Artifact).where(
                    Artifact.universe_id == universe_id, Artifact.type == "entity"
                )
            ).all()

            id_to_name = {e.id: e.name for e in entities}

            # 2. Get all claims for this universe
            claims = session.exec(
                select(Artifact).where(
                    Artifact.universe_id == universe_id, Artifact.type == "claim"
                )
            ).all()

            # 3. Build the graph
            graph = {}
            for e in entities:
                graph[e.name] = {
                    "entity": e.name,
                    "facts": [],
                    "related_entities": set(),
                }

            for c in claims:
                payload = json.loads(c.payload_json or "{}")
                subj_id = payload.get("subject_id")
                subj_name = id_to_name.get(
                    subj_id, payload.get("subject_name", "Unknown")
                )

                if subj_name not in graph:
                    # This should rarely happen if all entities were retrieved,
                    # but handles dynamically added entities in claims.
                    graph[subj_name] = {
                        "entity": subj_name,
                        "facts": [],
                        "related_entities": set(),
                    }

                # Resolve object
                obj_val = payload.get("object_literal")
                obj_id = payload.get("object_id")
                if obj_id:
                    obj_val = id_to_name.get(obj_id, f"Entity({obj_id})")
                    graph[subj_name]["related_entities"].add(obj_val)

                # Add fact
                graph[subj_name]["facts"].append(
                    {
                        "predicate": payload.get("predicate", "related_to"),
                        "object": obj_val,
                        "support": 1,  # TODO: Artifact should have support count if needed
                        "status": c.verification_status,
                        "reference": c.source_reference,
                    }
                )

            # 3b. Add relations from ArtifactRelation
            relations = session.exec(
                select(ArtifactRelation).where(ArtifactRelation.universe_id == universe_id)
            ).all()

            for r in relations:
                subj_name = id_to_name.get(r.from_artifact_id)
                obj_name = id_to_name.get(r.to_artifact_id)

                if subj_name and obj_name:
                    if subj_name not in graph:
                        graph[subj_name] = {
                            "entity": subj_name,
                            "facts": [],
                            "related_entities": set(),
                        }
                    if obj_name not in graph:
                        graph[obj_name] = {
                            "entity": obj_name,
                            "facts": [],
                            "related_entities": set(),
                        }

                    graph[subj_name]["related_entities"].add(obj_name)
                    graph[subj_name]["facts"].append(
                             {
                                 "predicate": r.relation_type,
                                 "object": obj_name,
                                 "support": 1,
                                 "status": "VERIFIED",
                                 "reference": r.description,
                             }
                         )


            # 4. Add specifications/properties
            specs = session.exec(
                select(Artifact).where(
                    Artifact.universe_id == universe_id, Artifact.type == "specification"
                )
            ).all()

            for s in specs:
                payload = json.loads(s.payload_json or "{}")
                parent_id = payload.get("parent_id")
                if parent_id in id_to_name:
                    parent_name = id_to_name[parent_id]
                    if parent_name not in graph:
                        # This should rarely happen if all entities were retrieved,
                        # but handles dynamically added entities in specs.
                        graph[parent_name] = {
                            "entity": parent_name,
                            "facts": [],
                            "related_entities": set(),
                        }

                    graph[parent_name]["facts"].append({
                        "predicate": payload.get("key", "property"),
                        "object": payload.get("value"),
                        "support": 1,
                        "status": s.verification_status,
                        "reference": s.source_reference,
                    })

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
            f"({c['subject']} --{c['predicate']}--> {c['object']}) "
            f"[Support: {c['support']}]"
            for c in claims
        ]
        return "\n".join(lines)
