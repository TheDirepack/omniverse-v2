import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
from sqlmodel import Session, select

from app.core.router import calculate_candidate_hash, _clean_error, ModelRouter, router
from app.db.schema import AgentRouteFallback, ProviderConfig, ProviderKey, CandidateHealth

def test_calculate_candidate_hash():
    # Test consistency
    hash1 = calculate_candidate_hash(1, 10, "gpt-4")
    hash2 = calculate_candidate_hash(1, 10, "gpt-4")
    assert hash1 == hash2
    
    # Test difference
    hash3 = calculate_candidate_hash(2, 10, "gpt-4")
    assert hash1 != hash3
    
    hash4 = calculate_candidate_hash(1, 11, "gpt-4")
    assert hash1 != hash4
    
    hash5 = calculate_candidate_hash(1, 10, "gpt-3.5")
    assert hash1 != hash5

def test_clean_error():
    # Simple error
    assert _clean_error(Exception("Simple error")) == "Simple error"
    
    # Error with newline
    assert _clean_error(Exception("First line\nSecond line")) == "First line"
    
    # Error with " - {"
    assert _clean_error(Exception("Main error - {details: 123}")) == "Main error"
    
    # litellm error prefix
    assert _clean_error(Exception("litellm.APIError: Rate limit reached")) == "litellm.APIError: Rate limit reached"
    assert _clean_error(Exception("litellm.APIError: Error 1\nlitellm.APIError: Error 2")) == "litellm.APIError: Error 1"

class TestModelRouterHealth:
    def test_get_health_new(self):
        router_inst = ModelRouter()
        mock_session = MagicMock(spec=Session)
        mock_session.get.return_value = None
        
        health = router_inst._get_health(mock_session, 1, 10, "gpt-4")
        
        assert health.provider_id == 1
        assert health.key_id == 10
        assert health.model == "gpt-4"
        assert health.failure_count == 0
        mock_session.add.assert_called_once_with(health)
        mock_session.commit.assert_called_once()

    def test_get_health_existing(self):
        router_inst = ModelRouter()
        mock_session = MagicMock(spec=Session)
        existing_health = CandidateHealth(
            candidate_hash="somehash", provider_id=1, key_id=10, model="gpt-4", failure_count=2
        )
        mock_session.get.return_value = existing_health
        
        health = router_inst._get_health(mock_session, 1, 10, "gpt-4")
        
        assert health == existing_health
        assert health.failure_count == 2
        mock_session.add.assert_not_called()

    def test_report_failure_increment(self):
        router_inst = ModelRouter()
        mock_session = MagicMock(spec=Session)
        health = CandidateHealth(
            candidate_hash="hash", provider_id=1, key_id=10, model="gpt-4", failure_count=0
        )
        
        with patch.object(router_inst, '_get_health', return_value=health):
            router_inst._report_failure(mock_session, 1, 10, "gpt-4")
            
        assert health.failure_count == 1
        assert health.last_failure_at is not None
        assert health.disabled_until is None
        mock_session.commit.assert_called()

    def test_report_failure_threshold_disables(self):
        router_inst = ModelRouter()
        mock_session = MagicMock(spec=Session)
        health = CandidateHealth(
            candidate_hash="hash", provider_id=1, key_id=10, model="gpt-4", failure_count=4
        )
        
        with patch.object(router_inst, '_get_health', return_value=health):
            router_inst._report_failure(mock_session, 1, 10, "gpt-4")
            
        assert health.failure_count == 5
        assert health.disabled_until is not None
        assert health.disabled_until > datetime.utcnow()

    def test_report_failure_decay(self):
        router_inst = ModelRouter()
        mock_session = MagicMock(spec=Session)
        last_failure = datetime.utcnow() - timedelta(hours=2)
        health = CandidateHealth(
            candidate_hash="hash", provider_id=1, key_id=10, model="gpt-4", 
            failure_count=3, last_failure_at=last_failure
        )
        
        with patch.object(router_inst, '_get_health', return_value=health):
            router_inst._report_failure(mock_session, 1, 10, "gpt-4")
            
        # failure_count should be 3 - 1 + 1 = 3
        assert health.failure_count == 3
        mock_session.commit.assert_called()

    def test_report_success(self):
        router_inst = ModelRouter()
        mock_session = MagicMock(spec=Session)
        health = CandidateHealth(
            candidate_hash="hash", provider_id=1, key_id=10, model="gpt-4", 
            failure_count=5, disabled_until=datetime.utcnow() + timedelta(hours=1)
        )
        
        with patch.object(router_inst, '_get_health', return_value=health):
            router_inst._report_success(mock_session, 1, 10, "gpt-4")
            
        assert health.failure_count == 0
        assert health.disabled_until is None
        mock_session.commit.assert_called()

class TestModelRouterRouting:
    @pytest.fixture
    def router_inst(self):
        return ModelRouter()

    @pytest.fixture
    def mock_session(self):
        return MagicMock(spec=Session)

    @pytest.mark.asyncio
    async def test_routing_specific_task(self, router_inst, mock_session):
        # Mock litellm
        with patch("app.core.router.litellm.acompletion", new_callable=AsyncMock) as mock_completion, \
             patch("app.core.router.Session", return_value=mock_session), \
             patch("app.core.router.settings_engine"), \
             patch("app.core.router.operational_engine"), \
             patch("app.core.router.engine"):
            
            # Setup routing: task "MY_TASK" -> provider 1
            route = AgentRouteFallback(task_type="MY_TASK", provider_id=1, models="gpt-4", priority=0)
            key = ProviderKey(id=10, api_key="key-1", priority=0)
            
            # We need to return:
            # 1. Routes for task -> [route]
            # 2. Keys for provider -> [key]
            mock_session.exec.return_value.all.side_effect = [
                [route], 
                [key],
            ]
            
            # Setup provider
            provider = ProviderConfig(id=1, provider_type="openai", base_url="http://test", models="gpt-4")
            mock_session.get.return_value = provider
            
            # Mock health check
            with patch.object(router_inst, '_get_health') as mock_health:
                mock_health.return_value = CandidateHealth(
                    candidate_hash="h", provider_id=1, key_id=10, model="gpt-4", failure_count=0
                )
                
                mock_completion.return_value = MagicMock(choices=[MagicMock(message=MagicMock(content="hi"))])
                
                res = await router_inst.call_llm_with_tools("MY_TASK", [{"role": "user", "content": "hi"}], [])
                
                assert res[1] == "openai/gpt-4"
                mock_completion.assert_called_once()
                assert mock_completion.call_args[1]["api_key"] == "key-1"

    @pytest.mark.asyncio
    async def test_routing_default_fallback(self, router_inst, mock_session):
        with patch("app.core.router.litellm.acompletion", new_callable=AsyncMock) as mock_completion, \
             patch("app.core.router.Session", return_value=mock_session), \
             patch("app.core.router.settings_engine"), \
             patch("app.core.router.operational_engine"), \
             patch("app.core.router.engine"):
            
            # No routes for "UNKNOWN", but routes for "DEFAULT"
            route_default = AgentRouteFallback(task_type="DEFAULT", provider_id=1, models="gpt-4", priority=0)
            key = ProviderKey(id=10, api_key="def-key", priority=0)
            
            # 1. Routes for "UNKNOWN" -> []
            # 2. Routes for "DEFAULT" -> [route_default]
            # 3. Keys for provider -> [key]
            mock_session.exec.return_value.all.side_effect = [
                [], [route_default], [key]
            ]
            
            provider = ProviderConfig(id=1, provider_type="openai", base_url="http://test", models="gpt-4")
            mock_session.get.return_value = provider
            
            with patch.object(router_inst, '_get_health') as mock_health:
                mock_health.return_value = CandidateHealth(
                    candidate_hash="h", provider_id=1, key_id=10, model="gpt-4", failure_count=0
                )
                mock_completion.return_value = MagicMock(choices=[MagicMock(message=MagicMock(content="hi"))])
                
                res = await router_inst.call_llm_with_tools("UNKNOWN", [{"role": "user", "content": "hi"}], [])
                
                assert res[1] == "openai/gpt-4"
                assert mock_completion.call_args[1]["api_key"] == "def-key"

    @pytest.mark.asyncio
    async def test_independence_guard(self, router_inst, mock_session):
        with patch("app.core.router.litellm.acompletion", new_callable=AsyncMock) as mock_completion, \
             patch("app.core.router.Session", return_value=mock_session), \
             patch("app.core.router.settings_engine"), \
             patch("app.core.router.operational_engine"), \
             patch("app.core.router.engine"):
            
            # Routes: Route1(Prov1), Route2(Prov2)
            route1 = AgentRouteFallback(task_type="TASK", provider_id=1, models="gpt-4", priority=0)
            route2 = AgentRouteFallback(task_type="TASK", provider_id=2, models="gpt-4", priority=1)
            
            key1 = ProviderKey(id=10, api_key="k1", priority=0)
            key2 = ProviderKey(id=20, api_key="k2", priority=0)
            
            # 1. Routes for "TASK" -> [route1, route2]
            # 2. Keys for prov2 (since prov1 is excluded) -> [key2]
            mock_session.exec.return_value.all.side_effect = [
                [route1, route2], 
                [key2], 
            ]
            
            provider1 = ProviderConfig(id=1, provider_type="openai", base_url="url1", models="gpt-4")
            provider2 = ProviderConfig(id=2, provider_type="openai", base_url="url2", models="gpt-4")
            mock_session.get.side_effect = [provider2] # only provider 2 is needed
            
            with patch.object(router_inst, '_get_health') as mock_health:
                mock_health.return_value = CandidateHealth(candidate_hash="h", provider_id=2, key_id=20, model="gpt-4", failure_count=0)
                mock_completion.return_value = MagicMock(choices=[MagicMock(message=MagicMock(content="hi"))])
                
                # Exclude provider 1, should use provider 2
                res = await router_inst.call_llm_with_tools(
                    "TASK", [{"role": "user", "content": "hi"}], [], exclude_provider_id=1
                )
                
                assert res[1] == "openai/gpt-4"
                assert mock_completion.call_args[1]["api_base"] == "url2"
