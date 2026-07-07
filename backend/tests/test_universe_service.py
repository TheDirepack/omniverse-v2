import json
from unittest.mock import ANY, patch

import pytest

from app.db.schema import Entity, Universe, UniverseRelation
from app.services.universe_service import UniverseService


class TestCreateUniverse:
    def test_create_basic(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        u = svc.create_universe(name="TestVerse")
        assert u.id is not None
        assert u.name == "TestVerse"
        assert u.slug == "testverse"
        assert u.is_explored is False

    def test_create_with_all_fields(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        parent = svc.create_universe(name="Parent")
        u = svc.create_universe(
            name="Child",
            franchise="F",
            category="C",
            continuity="C",
            era="E",
            parent_id=parent.id,
        )
        assert u.franchise == "F"
        assert u.parent_id == parent.id

    def test_create_duplicate_slug(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        svc.create_universe(name="Test Verse")
        u2 = svc.create_universe(name="Test Verse")
        assert u2.slug == "test_verse_1"


class TestGetUniverse:
    def test_get_by_name(self, ephemeral_db):
        UniverseService(session=ephemeral_db).create_universe(name="FindMe")
        svc = UniverseService(session=ephemeral_db)
        u = svc.get_universe("FindMe")
        assert u is not None
        assert u.name == "FindMe"

    def test_get_by_name_missing(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        assert svc.get_universe("Nope") is None

    def test_get_by_id(self, ephemeral_db):
        created = UniverseService(session=ephemeral_db).create_universe(name="ByID")
        svc = UniverseService(session=ephemeral_db)
        u = svc.get_universe_by_id(created.id)
        assert u is not None
        assert u.id == created.id

    def test_get_by_id_missing(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        assert svc.get_universe_by_id(99999) is None

    def test_get_by_uuid(self, ephemeral_db):
        created = UniverseService(session=ephemeral_db).create_universe(name="ByUUID")
        svc = UniverseService(session=ephemeral_db)
        u = svc.get_universe_by_uuid(created.uuid)
        assert u is not None
        assert u.uuid == created.uuid

    def test_get_all(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        svc.create_universe(name="A")
        svc.create_universe(name="B")
        all_u = svc.get_all_universes()
        assert len(all_u) >= 2

    def test_get_all_with_fields(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        svc.create_universe(name="FieldTest")
        results = svc.get_all_universes(fields=["name"])
        assert len(results) >= 1


class TestImportFromRegistry:
    @patch("app.services.universe_service.Path.exists", return_value=False)
    def test_no_registry_file(self, mock_exists, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        assert svc.import_from_registry("pokemon") is None

    @patch("app.services.universe_service.Path.exists", return_value=True)
    @patch("builtins.open")
    def test_entry_not_found(self, mock_open, mock_exists, ephemeral_db):
        mock_open.return_value.__enter__.return_value.read.return_value = "[]"
        svc = UniverseService(session=ephemeral_db)
        assert svc.import_from_registry("nonexistent") is None

    @patch("app.services.universe_service.Path.exists", return_value=True)
    @patch("builtins.open")
    def test_import_new_world(self, mock_open, mock_exists, ephemeral_db):
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(
            [{"id": "test_world", "name": "Test World", "franchise": "TF"}]
        )
        svc = UniverseService(session=ephemeral_db)
        u = svc.import_from_registry("test_world")
        assert u is not None
        assert u.name == "Test World"
        assert u.slug == "test_world"

    @patch("app.services.universe_service.Path.exists", return_value=True)
    @patch("builtins.open")
    def test_import_already_exists_by_slug(self, mock_open, mock_exists, ephemeral_db):
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(
            [{"id": "existing_slug", "name": "New Name"}]
        )
        svc = UniverseService(session=ephemeral_db)
        repo_svc = UniverseService(session=ephemeral_db)
        repo_svc.create_universe(name="Existing Name")
        # Manually set slug to match
        u = repo_svc.get_universe("Existing Name")
        u.slug = "existing_slug"
        ephemeral_db.add(u)
        ephemeral_db.commit()

        result = svc.import_from_registry("existing_slug")
        assert result is not None
        assert result.name == "Existing Name"

    @patch("app.services.universe_service.Path.exists", return_value=True)
    @patch("builtins.open")
    def test_import_with_parent(self, mock_open, mock_exists, ephemeral_db):
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(
            [{"id": "parent_world", "name": "Parent"}, {"id": "child_world", "name": "Child", "parent": "parent_world"}]
        )
        svc = UniverseService(session=ephemeral_db)
        parent = svc.import_from_registry("parent_world")
        assert parent is not None

        child = svc.import_from_registry("child_world")
        assert child is not None
        assert child.parent_id == parent.id


class TestImportAllFromRegistry:
    @patch("app.services.universe_service.Path.exists", return_value=False)
    def test_no_file(self, mock_exists, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        imported, skipped = svc.import_all_from_registry()
        assert imported == 0
        assert skipped == 0

    @patch("app.services.universe_service.Path.exists", return_value=True)
    @patch("builtins.open")
    def test_import_all_success(self, mock_open, mock_exists, ephemeral_db):
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(
            [
                {"id": "w1", "name": "World 1", "franchise": "F1"},
                {"id": "w2", "name": "World 2", "parent": "w1"},
            ]
        )
        svc = UniverseService(session=ephemeral_db)
        imported, skipped = svc.import_all_from_registry()
        assert imported == 2
        assert skipped == 0

    @patch("app.services.universe_service.Path.exists", return_value=True)
    @patch("builtins.open")
    def test_import_skips_existing(self, mock_open, mock_exists, ephemeral_db):
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(
            [{"id": "dup", "name": "Duplicate"}]
        )
        svc = UniverseService(session=ephemeral_db)
        svc.create_universe(name="Duplicate")
        imported, skipped = svc.import_all_from_registry()
        assert imported == 0
        assert skipped == 1


class TestFindDuplicates:
    def test_no_duplicates(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        svc.create_universe(name="Unique World")
        result = svc.find_duplicates("Totally Different")
        assert result == []

    def test_exact_match(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        svc.create_universe(name="Exact Match")
        result = svc.find_duplicates("Exact Match")
        assert len(result) == 1
        assert result[0]["similarity"] == 1.0

    def test_substring_match(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        svc.create_universe(name="The World of Warcraft")
        result = svc.find_duplicates("World of Warcraft")
        assert len(result) == 1
        assert result[0]["similarity"] == 0.85


class TestNameSimilarity:
    def test_empty_inputs(self):
        svc = UniverseService()
        assert svc._name_similarity("", "foo") == 0.0
        assert svc._name_similarity("foo", "") == 0.0
        assert svc._name_similarity("", "") == 0.0

    def test_exact(self):
        svc = UniverseService()
        assert svc._name_similarity("hello", "hello") == 1.0

    def test_substring(self):
        svc = UniverseService()
        assert svc._name_similarity("hello", "hello world") == 0.85
        assert svc._name_similarity("hello world", "hello") == 0.85

    def test_token_overlap(self):
        svc = UniverseService()
        sim = svc._name_similarity("war hammer", "war hammer 40k")
        assert sim > 0.5

    def test_no_overlap(self):
        svc = UniverseService()
        assert svc._name_similarity("abc", "xyz") == 0.0


class TestMergeWorlds:
    def test_merge_success(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        keep = svc.create_universe(name="Keep")
        merge = svc.create_universe(name="Merge")
        result = svc.merge_worlds(keep.id, merge.id)
        assert result["status"] == "success"

    def test_merge_not_found(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        result = svc.merge_worlds(1, 99999)
        assert result["status"] == "error"

    def test_merge_moves_entities(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        keep = svc.create_universe(name="Keep")
        merge = svc.create_universe(name="Merge")
        e = Entity(name="SharedEntity", entity_type="T", universe_id=merge.id)
        ephemeral_db.add(e)
        ephemeral_db.commit()
        result = svc.merge_worlds(keep.id, merge.id)
        assert result["status"] == "success"
        moved = ephemeral_db.exec(
            __import__("sqlmodel").select(Entity).where(Entity.name == "SharedEntity")
        ).first()
        assert moved.universe_id == keep.id


class TestMarkExplored:
    def test_mark_explored(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        u = svc.create_universe(name="Explore Me")
        assert u.is_explored is False
        svc.mark_explored(u.id)
        reloaded = svc.get_universe_by_id(u.id)
        assert reloaded.is_explored is True

    def test_reset_explored(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        u = svc.create_universe(name="Reset Me")
        svc.mark_explored(u.id)
        assert svc.reset_explored(u.id) is True
        reloaded = svc.get_universe_by_id(u.id)
        assert reloaded.is_explored is False

    def test_reset_explored_not_found(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        assert svc.reset_explored(99999) is False

    def test_reset_all_explored(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        u1 = svc.create_universe(name="U1")
        u2 = svc.create_universe(name="U2")
        svc.mark_explored(u1.id)
        svc.mark_explored(u2.id)
        count = svc.reset_all_explored()
        assert count == 2
        r1 = svc.get_universe_by_id(u1.id)
        r2 = svc.get_universe_by_id(u2.id)
        assert r1.is_explored is False
        assert r2.is_explored is False

    def test_reset_all_no_explored(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        svc.create_universe(name="U1")
        assert svc.reset_all_explored() == 0


class TestUpdateSummary:
    def test_update_summary(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        u = svc.create_universe(name="Summarize")
        svc.update_summary(u.id, "New summary text")
        reloaded = svc.get_universe_by_id(u.id)
        assert reloaded.summary == "New summary text"

    def test_update_summary_missing(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        svc.update_summary(99999, "should not crash")


class TestDeleteUniverse:
    def test_delete(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        u = svc.create_universe(name="Delete Me")
        uid = u.id
        svc.delete_universe(uid)
        assert svc.get_universe_by_id(uid) is None

    def test_delete_missing(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        svc.delete_universe(99999)


class TestClose:
    def test_close_without_session(self, ephemeral_db):
        svc = UniverseService()
        svc.close()
        assert svc._repo is None

    def test_close_with_session(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        svc.close()
        # session not ours to close; _repo never created
        assert svc._repo is None


class TestEntityCanonical:
    def test_set_entity_canonical(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        u = svc.create_universe(name="Canon")
        e = Entity(name="Hero", entity_type="Person", universe_id=u.id)
        ephemeral_db.add(e)
        ephemeral_db.commit()
        ephemeral_db.refresh(e)
        svc.set_entity_canonical(e.id)
        reloaded = ephemeral_db.get(Entity, e.id)
        assert reloaded.canonical is True

    def test_set_entity_canonical_link(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        u = svc.create_universe(name="Canon2")
        e1 = Entity(name="HeroPrime", entity_type="Person", universe_id=u.id)
        e2 = Entity(name="HeroAlias", entity_type="Person", universe_id=u.id)
        ephemeral_db.add_all([e1, e2])
        ephemeral_db.commit()
        ephemeral_db.refresh(e1)
        ephemeral_db.refresh(e2)
        svc.set_entity_canonical(e2.id, e1.id)
        reloaded = ephemeral_db.get(Entity, e2.id)
        assert reloaded.canonical_entity_id == e1.id


class TestGetRelatedUniverses:
    def test_get_related(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        u1 = svc.create_universe(name="U1")
        u2 = svc.create_universe(name="U2")
        svc.create_universe_relation(u1.id, u2.id, "ALT")
        related = svc.get_related_universes(u1.id)
        assert len(related) == 1
        assert related[0].name == "U2"

    def test_get_related_none(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        u = svc.create_universe(name="Lonely")
        assert svc.get_related_universes(u.id) == []


class TestGetClaims:
    def test_get_claims(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        u = svc.create_universe(name="Claims")
        e = Entity(name="Test", entity_type="T", universe_id=u.id)
        ephemeral_db.add(e)
        ephemeral_db.commit()
        ephemeral_db.refresh(e)
        from app.db.schema import Claim
        c = Claim(subject_id=e.id, predicate="test", object_literal="val", universe_scope=u.id, status="VERIFIED")
        ephemeral_db.add(c)
        ephemeral_db.commit()
        result = svc.get_claims(universe_ids=str(u.id))
        assert len(result) == 1

    def test_get_claims_with_fields(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        u = svc.create_universe(name="Claims2")
        e = Entity(name="Test", entity_type="T", universe_id=u.id)
        ephemeral_db.add(e)
        ephemeral_db.commit()
        ephemeral_db.refresh(e)
        from app.db.schema import Claim
        c = Claim(subject_id=e.id, predicate="test", object_literal="val", universe_scope=u.id, status="VERIFIED")
        ephemeral_db.add(c)
        ephemeral_db.commit()
        result = svc.get_claims(universe_ids=str(u.id), fields=["predicate", "status"])
        assert len(result) >= 1
        for r in result:
            assert isinstance(r, dict)
            assert "predicate" in r or "status" in r

    def test_get_claims_no_filter(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        result = svc.get_claims()
        assert isinstance(result, list)

    def test_get_verified_claims(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        u = svc.create_universe(name="VC")
        e = Entity(name="Test", entity_type="T", universe_id=u.id)
        ephemeral_db.add(e)
        ephemeral_db.commit()
        ephemeral_db.refresh(e)
        from app.db.schema import Claim
        c = Claim(subject_id=e.id, predicate="test", object_literal="v", universe_scope=u.id, status="VERIFIED")
        ephemeral_db.add(c)
        ephemeral_db.commit()
        result = svc.get_verified_claims(u.id)
        assert len(result) == 1


class TestGetUniverseRelations:
    def test_get_relations_direction(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        u1 = svc.create_universe(name="R1")
        u2 = svc.create_universe(name="R2")
        svc.create_universe_relation(u1.id, u2.id, "PRECEDES")
        out = svc.get_universe_relations(u1.id, direction="out")
        assert len(out) == 1
        both = svc.get_universe_relations(u1.id, direction="both")
        assert len(both) == 1


class TestUniverseServiceSessionHandling:
    def test_service_without_session_closes_internal_session(self, ephemeral_db):
        svc = UniverseService()
        svc.create_universe(name="NoSession")
        svc.close()
        assert svc._repo is None

    def test_service_with_external_session_does_not_close_it(self, ephemeral_db):
        svc = UniverseService(session=ephemeral_db)
        svc.create_universe(name="WithSession")
        svc.close()
        assert ephemeral_db.is_active
