from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import Session, select

from app.agents.prompts import get_researcher_prompt
from app.core.context import set_current_universe
from app.core.tools import (
    tool_fetch_page,
    tool_query_artifacts,
    tool_upsert_artifacts,
    tool_web_search,
)
from app.db.schema import Artifact, ArtifactRelation, Evidence, EvidenceChunk, Universe
from app.db.session import engine
from app.services.knowledge_retriever import KnowledgeRetrieverService


@pytest.fixture
def setup_universe(clean_db):

    from app.db.session import init_db
    init_db(engine)
    session = clean_db
    # Create a test universe
    u = Universe(name="TestUniverse")
    session.add(u)
    session.commit()
    session.refresh(u)

    # Create artifacts (replacing entities)
    a1 = Artifact(name="Entity1", type="entity", universe_id=u.id)
    a2 = Artifact(name="Entity2", type="entity", universe_id=u.id)
    session.add_all([a1, a2])
    session.commit()

    # Create relation (replacing claim)
    r = ArtifactRelation(
        from_artifact_id=a1.id,
        to_artifact_id=a2.id,
        relation_type="LIVES_IN",
        universe_id=u.id,
        description="test.com:1",
    )
    session.add(r)
    session.commit()

    yield u



def test_knowledge_retriever_service(setup_universe):
    u = setup_universe
    retriever = KnowledgeRetrieverService()

    # Test graph retrieval
    graph = retriever.get_universe_knowledge_graph(u.id)
    assert "Entity1" in graph
    assert graph["Entity1"]["facts"][0]["predicate"] == "LIVES_IN"
    assert graph["Entity1"]["facts"][0]["object"] == "Entity2"
    assert "Entity2" in graph["Entity1"]["related_entities"]

    # Test semantic claims retrieval
    claims = retriever.get_semantic_claims(u.id)
    assert len(claims) == 1
    assert claims[0]["subject"] == "Entity1"
    assert claims[0]["object"] == "Entity2"


@pytest.mark.asyncio
async def test_tool_query_artifacts(setup_universe):
    u = setup_universe
    set_current_universe(u.name)

    result = await tool_query_artifacts({})
    assert "Entity1" in result
    assert "Lives In" in result



@pytest.mark.asyncio
async def test_tool_upsert_artifacts_evidence(setup_universe):
    u = setup_universe
    set_current_universe(u.name)

    # Upsert an artifact with a source
    item = {
        "type": "claim",
        "name": "Entity1 HAS_POWER Flying",
        "payload": {"subject": "Entity1", "predicate": "HAS_POWER", "object": "Flying"},
        "source_wiki": "http://wiki.test/Entity1",
        "source_reference": "Section 2",
    }

    result = await tool_upsert_artifacts({"items": [item]})
    assert "Integrated" in result

    with Session(engine) as session:
        # Check if evidence was created
        evidence = session.exec(
            select(Evidence).where(Evidence.source_url == "http://wiki.test/Entity1")
        ).first()
        assert evidence is not None

        chunk = session.exec(
            select(EvidenceChunk).where(EvidenceChunk.evidence_id == evidence.id)
        ).first()
        assert chunk is not None
        assert chunk.content == "Section 2"

        # Check if artifact is linked to chunk
        artifact = session.exec(
            select(Artifact).where(Artifact.name == "Entity1 HAS_POWER Flying")
        ).first()
        assert artifact is not None
        assert artifact.evidence_id == evidence.id
        assert chunk.evidence_id == evidence.id



@pytest.mark.asyncio
async def test_tool_web_search_parallel_multi_engine():
    with patch(
        "app.core.tools.web_searcher.perform_search", new_callable=AsyncMock
    ) as mock_search:
        # Mock a successful structured response
        mock_search.return_value = {
            "status": "SUCCESS",
            "engine": "google",
            "query": "test query",
            "results": [
                {"title": "Result 1", "url": "http://res1.com", "snippet": "Snippet 1"},
                {"title": "Result 2", "url": "http://res2.com", "snippet": "Snippet 2"},
            ],
        }

        # Test batching and multiple engines
        args = {"queries": ["q1", "q2"], "engine": "google,brave", "max_results": 5}

        result = await tool_web_search(args)

        # We expect 2 queries * 2 engines = 4 calls
        assert mock_search.call_count == 4
        assert "### Query 1: q1" in result
        assert "### Query 2: q2" in result
        assert "**google**" in result
        assert "**brave**" in result
        assert "[Result 1](http://res1.com)" in result


@pytest.mark.asyncio
async def test_tool_fetch_page_parallel():
    with patch(
        "app.core.tools.web_fetcher.fetch_page", new_callable=AsyncMock
    ) as mock_fetch:
        # Mock structured response
        mock_fetch.return_value = {
            "metadata": {
                "url": "http://test.com",
                "word_count": 100,
                "page_type": "ARTICLE",
            },
            "main_content": "The main content of the page.",
            "internal_links": [
                {
                    "url": "http://test.com/1",
                    "title": "Link1",
                    "tier": "High",
                    "score": 1,
                    "sections": ["Section 1"],
                }
            ],
            "research_signals": "Category: Test",
            "freshness": "[SOURCE FRESHNESS SIGNALS]\nFresh",
        }

        args = {"urls": ["http://url1.com", "http://url2.com"]}
        result = await tool_fetch_page(args)

        assert mock_fetch.call_count == 2
        assert "--- Content from http://url1.com" in result
        assert "--- Content from http://url2.com" in result
        assert "[MAIN ARTICLE]\nThe main content of the page." in result
        assert "Words: 100" in result
        assert "RECOMMENDED NEXT STEPS" in result


def test_get_researcher_prompt_assembly():
    prompt = get_researcher_prompt(
        entity="TestWorld",
        requirements="Find everything",
        verified_claims="(S --P--> O)",
        knowledge_graph='{"S": {"facts": []}}',
        notebook_data="Notebook claim X",
    )

    system = prompt["system"]
    assert "VERIFIED KNOWLEDGE BASE" in system
    assert "(S --P--> O)" in system
    assert "EXISTING KNOWLEDGE GRAPH" in system
    assert '{"S": {"facts": []}}' in system
    assert "STAGING DATABASE (Notebook Claims)" in system
    assert "Notebook claim X" in system
