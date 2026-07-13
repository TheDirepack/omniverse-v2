from unittest.mock import patch

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.context import set_current_universe
from app.core.tools import tool_save_notebook_entry, tool_upsert_artifacts
from app.db.schema import Artifact, Universe
from app.db.notebook_schema import (
    notebook_metadata,
)


@pytest.fixture
def mem_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    notebook_metadata.create_all(engine)
    return engine

@pytest.mark.asyncio
async def test_deterministic_promotion_flow(mem_engine):
    with patch("app.core.tools.engine", mem_engine), \
          patch("app.core.tools.notebook_engine", mem_engine):

        with Session(mem_engine) as session:
            u = Universe(name="PromoteWorld", slug="promote-world")
            session.add(u)
            session.commit()
            _ = u.id

        set_current_universe("PromoteWorld")

        res = await tool_save_notebook_entry({
            "title": "EntityX is a TypeY",
            "summary": "EntityX is a TypeY",
            "details": "subject: EntityX, predicate: is_a, object_val: TypeY",
            "kind": "Observation",
        })

        import re
        match = re.search(r"Notebook entry (\d+) saved successfully", res)
        if not match:
            pytest.fail(f"tool_save_notebook_entry did not return ID in expected format. Result: {res}")
        staging_id = int(match.group(1))

        upsert_args = {
            "items": [
                {
                    "type": "claim",
                    "name": "EntityX is a TypeY",
                    "payload": {
                        "subject": "EntityX",
                        "predicate": "is_a",
                        "object": "TypeY",
                        "staging_ref": staging_id
                    }
                }
            ]
        }

        await tool_upsert_artifacts(upsert_args)

        with Session(mem_engine) as session:
            claim = session.exec(select(Artifact).where(Artifact.type == "claim")).first()
            assert claim is not None
            assert claim.name == "EntityX is a TypeY"

            entities = session.exec(select(Artifact).where(Artifact.type == "entity")).all()
            entity_names = [e.name for e in entities]
            assert "EntityX" in entity_names
            assert "TypeY" in entity_names


@pytest.mark.asyncio
async def test_symmetric_entity_resolution(mem_engine):
    from app.core.context import set_current_universe
    set_current_universe("SymmetryWorld")
    with patch("app.core.tools.engine", mem_engine), \
          patch("app.core.tools.notebook_engine", mem_engine):
        with Session(mem_engine) as session:
            u = Universe(name="SymmetryWorld", slug="symmetry-world")
            session.add(u)
            session.commit()

            e = Artifact(name="Canonical Name", type="entity", universe_id=u.id)
            session.add(e)
            session.flush()

            session.commit()
            _ = u.id

        upsert_args = {
            "items": [
                {
                    "type": "claim",
                    "name": "Someone knows Canonical Name",
                    "payload": {
                        "subject": "Someone",
                        "predicate": "knows",
                        "object": "Canonical Name",
                    }
                }
            ]
        }

        await tool_upsert_artifacts(upsert_args)

        with Session(mem_engine) as session:
            claim = session.exec(select(Artifact).where(Artifact.type == "claim")).first()
            assert claim is not None

            payload = json.loads(claim.payload_json)
            assert payload["object_id"] == e.id


