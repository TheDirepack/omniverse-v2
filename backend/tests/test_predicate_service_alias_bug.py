from app.db.schema import Predicate, PredicateAlias
from app.services.ontology_service import OntologyService
from app.services.predicate_service import PredicateService


class TestPredicateAliasNormalization:
    """Regression tests for a silent (non-crashing) bug: PredicateAlias has
    no canonical_name column (only predicate_id, a real FK to Predicate),
    but PredicateService read/wrote a nonexistent canonical_name field.
    SQLModel silently drops unknown constructor kwargs rather than raising,
    so upsert_alias appeared to succeed while leaving predicate_id unset --
    every alias was a permanent no-op, and normalize() always fell through
    to returning the raw uppercased predicate unchanged. This directly
    undermines predicate normalization, the mechanism meant to prevent
    'USES'/'POWERED_BY'/'POWERED BY' from becoming three disconnected
    Predicate rows instead of one canonical form."""

    def test_upsert_alias_actually_sets_predicate_id(self, ephemeral_db):
        svc = PredicateService()
        svc.upsert_alias("uses", "POWERED_BY")

        stored = ephemeral_db.exec(
            __import__("sqlmodel")
            .select(PredicateAlias)
            .where(PredicateAlias.alias == "USES")
        ).first()
        assert stored is not None
        assert stored.predicate_id is not None, (
            "predicate_id was left unset -- the alias exists but points at nothing"
        )

        predicate = ephemeral_db.get(Predicate, stored.predicate_id)
        assert predicate is not None
        assert predicate.canonical_name == "POWERED_BY"

    def test_normalize_resolves_registered_alias(self, ephemeral_db):
        svc = PredicateService()
        svc.upsert_alias("uses", "POWERED_BY")

        result = svc.normalize("uses")
        assert result == "POWERED_BY", (
            f"expected the alias to resolve to its canonical predicate, got {result!r} "
            "-- this is the exact silent-failure mode of the original bug"
        )

    def test_normalize_handles_mixed_case_consistently(self, ephemeral_db):
        """The write path (upsert_alias) and read path (normalize) must
        agree on case folding, or a freshly-registered alias can never be
        found again."""
        svc = PredicateService()
        svc.upsert_alias("Uses", "POWERED_BY")  # mixed case on write

        assert svc.normalize("uses") == "POWERED_BY"  # lowercase on read
        assert svc.normalize("USES") == "POWERED_BY"  # uppercase on read
        assert svc.normalize("Uses") == "POWERED_BY"  # original case on read

    def test_upsert_alias_update_path_reuses_existing_row(self, ephemeral_db):
        """Registering the same alias twice (e.g. re-pointing it at a
        different canonical predicate) must update the existing row, not
        create a duplicate."""
        svc = PredicateService()
        svc.upsert_alias("uses", "POWERED_BY")
        svc.upsert_alias("uses", "OPERATES_VIA")

        all_aliases = ephemeral_db.exec(
            __import__("sqlmodel")
            .select(PredicateAlias)
            .where(PredicateAlias.alias == "USES")
        ).all()
        assert len(all_aliases) == 1, (
            "expected the alias row to be updated in place, not duplicated"
        )
        assert svc.normalize("uses") == "OPERATES_VIA"

    def test_normalize_falls_through_to_ontology_parent_chain(self, ephemeral_db):
        """An alias pointing at a child predicate must still resolve all
        the way to the root canonical predicate via the ontology's
        parent chain -- not just to the immediate (possibly non-root)
        predicate the alias points to."""
        ontology = OntologyService()
        ontology.define_relationship("POWERED_BY_FUSION", "POWERED_BY")

        svc = PredicateService()
        svc.upsert_alias("uses fusion engine", "POWERED_BY_FUSION")

        result = svc.normalize("uses fusion engine")
        assert result == "POWERED_BY", (
            f"expected traversal through the alias -> child predicate -> parent "
            f"predicate chain to reach the root canonical form, got {result!r}"
        )

    def test_normalize_unregistered_predicate_returns_raw_uppercased(
        self, ephemeral_db
    ):
        """No alias, no existing Predicate row -- normalize should just
        return the raw predicate uppercased, not crash or return None."""
        svc = PredicateService()
        result = svc.normalize("some brand new predicate")
        assert result == "SOME BRAND NEW PREDICATE"
