import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from app.main import app
from app.db import get_session


class TestMainApp:
    @pytest.fixture
    def client(self):
        app.dependency_overrides = {}
        with TestClient(app) as test_client:
            yield test_client
        app.dependency_overrides = {}
    
    def test_index_page(self, client):
        """Test home page loads correctly"""
        response = client.get("/")
        
        assert response.status_code == 200
        assert "Wikipedia Q&A Bot" in response.text
        assert "Connect to Slack" in response.text
    
    def test_install_redirect(self, client):
        """Test install endpoint redirects to OAuth"""
        with patch('app.main.slack_oauth') as mock_oauth:
            mock_oauth.generate_oauth_url.return_value = ("https://slack.com/oauth/v2/authorize?test", "test_state")
            
            response = client.get("/install", follow_redirects=False)
            
            assert response.status_code == 307
            assert "slack.com/oauth/v2/authorize" in response.headers["location"]
    
    def test_oauth_callback_success(self, client):
        """Test successful OAuth callback"""
        with patch('app.main.slack_oauth') as mock_oauth:
            mock_oauth.handle_oauth_callback = AsyncMock(return_value={
                "success": True,
                "team_id": "T123456",
                "team_name": "Test Team",
                "bot_user_id": "U123456",
                "installation_id": 1
            })
            
            with patch('app.main.oauth_states', {"test_state": True}):
                response = client.get("/oauth/callback?code=test_code&state=test_state")
            
        assert response.status_code == 200
        assert "Installation Successful" in response.text
        assert "Test Team" in response.text
    
    def test_oauth_callback_missing_params(self, client):
        """Test OAuth callback with missing parameters"""
        response = client.get("/oauth/callback")
        
        assert response.status_code == 400
    
    def test_oauth_callback_invalid_state(self, client):
        """Test OAuth callback with invalid state"""
        with patch('app.main.oauth_states', {}):
            response = client.get("/oauth/callback?code=test_code&state=invalid_state")
            
            assert response.status_code == 400
    
    def test_oauth_callback_error(self, client):
        """Test OAuth callback with error parameter"""
        response = client.get("/oauth/callback?error=access_denied")
        
        assert response.status_code == 400
    
    def test_logs_page_empty(self, client):
        """Test logs page with no data"""
        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = []

        def override_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_session

        response = client.get("/logs")

        assert response.status_code == 200
        assert "No Q&A logs yet" in response.text
    
    def test_logs_page_with_data(self, client):
        """Test logs page with Q&A data"""
        mock_installation = MagicMock()
        mock_installation.team_name = "Test Team"
        
        mock_qa_request = MagicMock()
        mock_qa_request.id = 1
        mock_qa_request.question = "What is AI?"
        mock_qa_request.answer = "AI is artificial intelligence."
        mock_qa_request.citations = '[]'
        mock_qa_request.user_id = "U123456"
        mock_qa_request.channel_id = "C123456"
        mock_qa_request.thread_ts = None
        mock_qa_request.conversation_id = None
        mock_qa_request.created_at = datetime(2023, 1, 1, 0, 0, 0)

        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = [(mock_qa_request, mock_installation)]

        def override_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_session

        response = client.get("/logs")

        assert response.status_code == 200
        assert "What is AI?" in response.text
        assert "AI is artificial intelligence." in response.text
        assert "Test Team" in response.text
    
    def test_api_installations(self, client):
        """Test API installations endpoint"""
        mock_installation = MagicMock()
        mock_installation.id = 1
        mock_installation.team_id = "T123456"
        mock_installation.team_name = "Test Team"
        mock_installation.bot_user_id = "U123456"
        mock_installation.is_active = True
        mock_installation.created_at = datetime(2023, 1, 1, 0, 0, 0)

        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = [mock_installation]

        def override_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_session

        response = client.get("/api/installations")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["team_id"] == "T123456"
        assert data[0]["team_name"] == "Test Team"
    
    def test_api_qa_requests(self, client):
        """Test API Q&A requests endpoint"""
        mock_qa_request = MagicMock()
        mock_qa_request.id = 1
        mock_qa_request.question = "What is AI?"
        mock_qa_request.answer = "AI is artificial intelligence."
        mock_qa_request.citations = '[]'
        mock_qa_request.user_id = "U123456"
        mock_qa_request.channel_id = "C123456"
        mock_qa_request.thread_ts = None
        mock_qa_request.conversation_id = None
        mock_qa_request.created_at = datetime(2023, 1, 1, 0, 0, 0)

        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = [mock_qa_request]

        def override_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_session

        response = client.get("/api/qa-requests")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["question"] == "What is AI?"
        assert data[0]["answer"] == "AI is artificial intelligence."
    
    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "wikipedia-slackbot"
    
    def test_slack_events_endpoint(self, client):
        """Test Slack events endpoint exists"""
        # This would normally require proper Slack signature verification
        # For now, just test that the endpoint exists
        response = client.post("/slack/events")
        
        # Should return 400 due to missing signature, but endpoint exists
        assert response.status_code == 400
    
    def test_slack_commands_endpoint(self, client):
        """Test Slack commands endpoint exists"""
        response = client.post("/slack/commands")
        
        # Should return 400 due to missing signature, but endpoint exists
        assert response.status_code == 400
    
    def test_slack_interactive_endpoint(self, client):
        """Test Slack interactive endpoint exists"""
        response = client.post("/slack/interactive")
        
        # Should return 400 due to missing signature, but endpoint exists
        assert response.status_code == 400
