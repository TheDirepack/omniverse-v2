import sys
from pathlib import Path

# Add backend to sys.path to allow importing app
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.append(str(BACKEND_DIR))

from sqlmodel import Session, select
from app.db.session import engine
from app.db.schema import Universe, Artifact, ArtifactRelation

def migrate(engine_override=None):
    print("Starting migration: Universe metadata to Artifacts...")
    from app.db.session import engine as default_engine
    engine = engine_override or default_engine
    with Session(engine) as session:
        universes = session.exec(select(Universe)).all()
        
        for universe in universes:
            print(f"Processing universe: {universe.name} (ID: {universe.id})")
            
            # 1. Create 'world' artifact for the universe
            world_artifact = Artifact(
                universe_id=universe.id,
                type="world",
                name=universe.name,
            )
            session.add(world_artifact)
            session.flush() # Get world_artifact.id

            # 2. Handle franchise
            if universe.franchise:
                franchise_artifact = Artifact(
                    universe_id=universe.id,
                    type="franchise",
                    name=universe.franchise,
                )
                session.add(franchise_artifact)
                session.flush()

                relation = ArtifactRelation(
                    universe_id=universe.id,
                    from_artifact_id=world_artifact.id,
                    to_artifact_id=franchise_artifact.id,
                    relation_type="PART_OF",
                )
                session.add(relation)

            # 3. Handle category
            if universe.category:
                category_artifact = Artifact(
                    universe_id=universe.id,
                    type="category",
                    name=universe.category,
                )
                session.add(category_artifact)
                session.flush()

                relation = ArtifactRelation(
                    universe_id=universe.id,
                    from_artifact_id=world_artifact.id,
                    to_artifact_id=category_artifact.id,
                    relation_type="PART_OF",
                )
                session.add(relation)

            # 4. Handle continuity
            if universe.continuity:
                continuity_artifact = Artifact(
                    universe_id=universe.id,
                    type="continuity",
                    name=universe.continuity,
                )
                session.add(continuity_artifact)
                session.flush()

                relation = ArtifactRelation(
                    universe_id=universe.id,
                    from_artifact_id=world_artifact.id,
                    to_artifact_id=continuity_artifact.id,
                    relation_type="PART_OF",
                )
                session.add(relation)

            # 5. Handle era
            if universe.era:
                era_artifact = Artifact(
                    universe_id=universe.id,
                    type="era",
                    name=universe.era,
                )
                session.add(era_artifact)
                session.flush()

                relation = ArtifactRelation(
                    universe_id=universe.id,
                    from_artifact_id=world_artifact.id,
                    to_artifact_id=era_artifact.id,
                    relation_type="PART_OF",
                )
                session.add(relation)

        session.commit()
        print("Migration completed successfully.")

if __name__ == "__main__":
    migrate()
