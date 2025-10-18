import pytest
import httpx
from urllib.parse import urlparse, parse_qs
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from app.oauth import SlackOAuth


class TestSlackOAuth:
    @pytest.fixture
    def oauth(self):
        with patch('app.oauth.SLACK_CLIENT_ID', 'test_client_id'), \
             patch('app.oauth.SLACK_CLIENT_SECRET', 'test_client_secret'), \
             patch('app.oauth.APP_BASE_URL', 'http://localhost:8000'), \
             patch('app.oauth.SECRET_KEY', 'test_secret_key'):
            return SlackOAuth()
    
    def test_generate_oauth_url(self, oauth):
        """Test OAuth URL generation"""
        url, state = oauth.generate_oauth_url()

        parsed = urlparse(url)
        query = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert parsed.netloc == "slack.com"
        assert parsed.path == "/oauth/v2/authorize"
        assert query["client_id"][0] == "test_client_id"
        assert query["redirect_uri"][0] == f"{oauth.base_url}/oauth/callback"
        scopes = set(query["scope"][0].split())
        assert scopes == {"commands", "chat:write", "app_mentions:read", "users:read", "team:read"}
        assert "state" in query
        assert query["state"][0] == state
    
    @pytest.mark.asyncio
    async def test_handle_oauth_callback_success(self, oauth):
        """Test successful OAuth callback handling"""
        mock_token_data = {
            "access_token": "xoxb-test-token",
            "bot_user_id": "U123456",
            "scope": "commands,chat:write",
            "authed_user": {"id": "U789012"}
        }
        
        mock_team_info = {
            "team": {
                "id": "T123456",
                "name": "Test Team"
            }
        }
        
        with patch.object(oauth, '_exchange_code_for_tokens', new=AsyncMock(return_value=mock_token_data)), \
             patch.object(oauth, '_get_team_info', new=AsyncMock(return_value=mock_team_info)), \
             patch.object(oauth, '_store_installation', new=AsyncMock()) as mock_store:
            
            mock_installation = MagicMock()
            mock_installation.id = 1
            mock_store.return_value = mock_installation
            
            result = await oauth.handle_oauth_callback("test_code", "test_state", "test_state")
            
            assert result["success"] is True
            assert result["team_id"] == "T123456"
            assert result["team_name"] == "Test Team"
            assert result["bot_user_id"] == "U123456"
            assert result["installation_id"] == 1
    
    @pytest.mark.asyncio
    async def test_handle_oauth_callback_invalid_state(self, oauth):
        """Test OAuth callback with invalid state"""
        with pytest.raises(HTTPException) as exc_info:
            await oauth.handle_oauth_callback("test_code", "invalid_state", "expected_state")
        
        assert exc_info.value.status_code == 400
    
    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_success(self, oauth):
        """Test successful code exchange for tokens"""
        mock_response_data = {
            "ok": True,
            "access_token": "xoxb-test-token",
            "bot_user_id": "U123456",
            "scope": "commands,chat:write",
            "authed_user": {"id": "U789012"}
        }
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            result = await oauth._exchange_code_for_tokens("test_code")
            
            assert result["access_token"] == "xoxb-test-token"
            assert result["bot_user_id"] == "U123456"
            mock_client.post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_error(self, oauth):
        """Test code exchange with API error"""
        mock_response_data = {
            "ok": False,
            "error": "invalid_code"
        }
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            with pytest.raises(HTTPException) as exc_info:
                await oauth._exchange_code_for_tokens("invalid_code")
            
            assert exc_info.value.status_code == 400
            assert exc_info.value.detail == "OAuth error: invalid_code"
    
    @pytest.mark.asyncio
    async def test_get_team_info_success(self, oauth):
        """Test successful team info retrieval"""
        mock_response_data = {
            "ok": True,
            "team": {
                "id": "T123456",
                "name": "Test Team"
            }
        }
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            result = await oauth._get_team_info("test_token")
            
            assert result["team"]["id"] == "T123456"
            assert result["team"]["name"] == "Test Team"
            mock_client.post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_store_installation_new(self, oauth):
        """Test storing new installation"""
        mock_token_data = {
            "access_token": "xoxb-test-token",
            "bot_user_id": "U123456",
            "scope": "commands,chat:write",
            "authed_user": {"id": "U789012"}
        }
        
        mock_team_info = {
            "team": {
                "id": "T123456",
                "name": "Test Team"
            }
        }
        
        with patch('app.oauth.get_db_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = None
            mock_get_session.return_value = mock_session
            
            with patch('app.oauth.Installation') as mock_installation_class:
                mock_installation = MagicMock()
                mock_installation.id = 1
                mock_installation_class.return_value = mock_installation
                
                result = await oauth._store_installation(mock_token_data, mock_team_info)
                
                assert result == mock_installation
                mock_session.add.assert_called_once_with(mock_installation)
                mock_session.commit.assert_called_once()
                mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_store_installation_existing(self, oauth):
        """Test updating existing installation"""
        mock_token_data = {
            "access_token": "xoxb-new-token",
            "bot_user_id": "U123456",
            "scope": "commands,chat:write",
            "authed_user": {"id": "U789012"}
        }
        
        mock_team_info = {
            "team": {
                "id": "T123456",
                "name": "Test Team"
            }
        }
        
        mock_existing = MagicMock()
        mock_existing.id = 1
        
        with patch('app.oauth.get_db_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = mock_existing
            mock_get_session.return_value = mock_session
            
            result = await oauth._store_installation(mock_token_data, mock_team_info)
            
            assert result == mock_existing
            assert mock_existing.bot_token == "xoxb-new-token"
            assert mock_existing.access_token == "xoxb-new-token"
            assert mock_existing.is_active is True
            mock_session.add.assert_not_called()  # Should not add new installation
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()
    
    def test_get_installation_by_team_id_found(self, oauth):
        """Test getting installation by team ID when found"""
        mock_installation = MagicMock()
        mock_installation.team_id = "T123456"
        
        with patch('app.oauth.get_db_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = mock_installation
            mock_get_session.return_value = mock_session
            
            result = oauth.get_installation_by_team_id("T123456")
            
            assert result == mock_installation
            mock_session.close.assert_called_once()
    
    def test_get_installation_by_team_id_not_found(self, oauth):
        """Test getting installation by team ID when not found"""
        with patch('app.oauth.get_db_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = None
            mock_get_session.return_value = mock_session
            
            result = oauth.get_installation_by_team_id("T999999")
            
            assert result is None
            mock_session.close.assert_called_once()
    
    def test_deactivate_installation_success(self, oauth):
        """Test successful installation deactivation"""
        mock_installation = MagicMock()
        mock_installation.is_active = True
        
        with patch('app.oauth.get_db_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = mock_installation
            mock_get_session.return_value = mock_session
            
            result = oauth.deactivate_installation("T123456")
            
            assert result is True
            assert mock_installation.is_active is False
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()
    
    def test_deactivate_installation_not_found(self, oauth):
        """Test deactivating non-existent installation"""
        with patch('app.oauth.get_db_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = None
            mock_get_session.return_value = mock_session
            
            result = oauth.deactivate_installation("T999999")
            
            assert result is False
            mock_session.commit.assert_not_called()
            mock_session.close.assert_called_once()
