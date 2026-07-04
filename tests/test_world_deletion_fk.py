import pytest
from sqlmodel import Session, select
from app.db.schema import Universe, Trait
from app.db.session import engine

def test_delete_world_with_traits(client, ephemeral_db):
    """
    Tests that deleting a world also deletes its traits to avoid FK constraints.
    """
    # 1. Setup: Create a world and a trait
    u = Universe(name="FKTestWorld", summary="test", is_explored=False)
    ephemeral_db.add(u)
    ephemeral_db.commit()
    ephemeral_db.refresh(u)
    
    t = Trait(
        universe_id=u.id,
        name="TestTrait",
        value="TestValue",
        category="TestCat"
    )
    ephemeral_db.add(t)
    ephemeral_db.commit()
    
    world_id = u.id
    
    # 2. Action: Delete the world via API
    response = client.delete(f"/api/worlds/{world_id}")
    
    # 3. Verification
    assert response.status_code == 200
    
    # Verify world is gone
    with Session(engine) as session:
        world = session.get(Universe, world_id)
        assert world is None
        
        # Verify trait is also gone (this is what caused the IntegrityError before)
        trait = session.exec(select(Trait).where(Trait.universe_id == world_id)).first()
        assert trait is None
