import pytest
from app.db.schema import Universe
from app.services.universe_service import UniverseService


class TestUniverseServiceRepoProperty:
    """Root-cause fix: UniverseService lost its .repo attribute in an
    earlier session-leak refactor (only _get_repo() was added, and it was
    never wired up), but 10 call sites across nodes.py, summarizer.py,
    runs.py, and three workflow modules still call uni_service.repo.X
    directly -- crashing with 'UniverseService object has no attribute
    repo' the moment the pipeline reached DB integration, exactly as seen
    in production: 'Manager[FAILED] Critical Execution Failure:
    UniverseService object has no attribute repo'."""

    def test_repo_property_exists_and_returns_repository(self, ephemeral_db):
        svc = UniverseService()
        from app.repositories.universe import UniverseRepository

        assert isinstance(svc.repo, UniverseRepository)

    def test_repo_is_cached_across_accesses(self, ephemeral_db):
        """Multiple .repo accesses on the same instance must reuse the same
        underlying repo/session -- the crash sites call .repo multiple times
        in sequence within a single function (get_by_names then
        update_batch), and both need to see the same uncommitted state."""
        svc = UniverseService()
        assert svc.repo is svc.repo

    def test_repo_coexists_with_clean_per_call_methods(self, ephemeral_db):
        """.repo must not interfere with the short-lived
        with-Session-per-call methods below it, and vice versa -- both
        access patterns are used by different parts of the codebase on
        freshly-constructed UniverseService() instances."""
        svc = UniverseService(session=ephemeral_db)
        u = svc.create_universe("TEST_RepoCoexist")
        assert u.id is not None

        via_repo = svc.repo.get_by_names(["TEST_RepoCoexist"])
        assert len(via_repo) == 1

        # Clean method afterward must still work (not broken by .repo usage)
        all_universes = svc.get_all_universes()
        assert any(x.name == "TEST_RepoCoexist" for x in all_universes)

        # .repo again -- must still work (not closed/broken by the clean
        # method call in between)
        via_repo_again = svc.repo.get_by_names(["TEST_RepoCoexist"])
        assert len(via_repo_again) == 1

    def test_get_repo_backward_compat_delegates_to_repo(self, ephemeral_db):
        svc = UniverseService()
        assert svc._get_repo() is svc.repo


@pytest.mark.asyncio
class TestDbIntegrationNodeMarkExploredBatch:
    """Reproduces the exact crash point from the production log: right
    after DB Architect finishes upserting claims, db_integration_node marks
    all integrated universes explored via uni_service.repo.get_by_names(...)
    then uni_service.repo.update_batch(...)."""

    async def test_get_by_names_then_update_batch_does_not_crash(self, ephemeral_db):
        ephemeral_db.add(Universe(name="battletech", is_explored=False))
        ephemeral_db.commit()

        uni_service = UniverseService()
        research_results = [{"name": "battletech"}]

        # This is the literal sequence from nodes.py's db_integration_node
        # that crashed with AttributeError before the fix.
        universes = uni_service.repo.get_by_names([r["name"] for r in research_results])
        assert len(universes) == 1
        for u in universes:
            u.is_explored = True
        uni_service.repo.update_batch(universes)

        # Verify the batch update actually persisted, not just that it
        # didn't crash.
        fresh_svc = UniverseService()
        reloaded = fresh_svc.repo.get_by_names(["battletech"])
        assert reloaded[0].is_explored is True

    async def test_summary_node_lookup_does_not_crash(self, ephemeral_db):
        """The second crash site in the same pipeline run: summary_node's
        uni_service.repo.get_by_names(verified_worlds) lookup."""
        ephemeral_db.add(Universe(name="halo", is_explored=True))
        ephemeral_db.commit()

        uni_service = UniverseService()
        universes = uni_service.repo.get_by_names(["halo"])
        universe_ids = [u.id for u in universes]
        assert len(universe_ids) == 1
