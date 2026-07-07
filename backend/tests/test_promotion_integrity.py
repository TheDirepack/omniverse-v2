import pytest
from unittest.mock import patch
from sqlmodel import Session, SQLModel, create_engine, select
from app.db.schema import Universe, Entity, EntityAlias, Claim
from app.db.unconfirmed_schema import UnconfirmedUniverse, UnconfirmedClaim, unconfirmed_metadata
from app.core.tools import tool_save_unconfirmed_claim, tool_upsert_claims
from app.services.universe_service import UniverseService
from app.core.context import set_current_universe

@pytest.fixture
def mem_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    unconfirmed_metadata.create_all(engine)
    return engine

@pytest.mark.asyncio
async def test_deterministic_promotion_flow(mem_engine):
    with patch("app.core.tools.engine", mem_engine), \
         patch("app.core.tools.unconfirmed_engine", mem_engine):
        
        with Session(mem_engine) as session:
            u = Universe(name="PromoteWorld", slug="promote-world")
            session.add(u)
            session.commit()
            u_id = u.id

        set_current_universe("PromoteWorld")
        
        res = await tool_save_unconfirmed_claim({
            "subject": "EntityX",
            "predicate": "is_a",
            "object_val": "TypeY",
        })
        
        import re
        match = re.search(r"IDs: ([\d, ]+)", res)
        if not match:
            pytest.fail(f"tool_save_unconfirmed_claim did not return IDs in expected format. Result: {res}")
        staging_id = int(match.group(1).split(',')[0].strip())

        upsert_args = {
            "items": [
                {
                    "subject": "EntityX",
                    "predicate": "is_a",
                    "object_val": "TypeY",
                    "staging_ref": staging_id
                }
            ]
        }
        
        await tool_upsert_claims(upsert_args)
        
        with Session(mem_engine) as session:
            claim = session.exec(select(Claim).where(Claim.subject_id != None)).first()
            assert claim is not None
            assert claim.source_unconfirmed_id == staging_id

    @pytest.mark.asyncio
    async def test_symmetric_entity_resolution(mem_engine):
        from app.core.context import set_current_universe
        set_current_universe("SymmetryWorld")
        with patch("app.core.tools.engine", mem_engine), \
             patch("app.core.tools.unconfirmed_engine", mem_engine):
            with Session(mem_engine) as session:
                u = Universe(name="SymmetryWorld", slug="symmetry-world")
                session.add(u)
                session.commit()
                
                e = Entity(name="Canonical Name", entity_type="Person", universe_id=u.id)
                session.add(e)
                session.flush()
                
                alias = EntityAlias(alias="Alias Name", entity_id=e.id, universe_id=u.id)
                session.add(alias)
                session.commit()
                u_id = u.id
        
            upsert_args = {
                "items": [
                    {
                        "subject": "Someone",
                        "predicate": "knows",
                        "object_val": "Alias Name",
                    }
                ]
            }
            
            await tool_upsert_claims(upsert_args)
            
            with Session(mem_engine) as session:
                claim = session.exec(select(Claim).where(Claim.subject_id != None)).first()
                assert claim is not None
                assert claim.object_entity_id == e.id
                assert claim.object_literal is None

