import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.slack_app import verify_slack_signature, _store_qa_request
from app.models import Installation


class TestSlackApp:
    def test_verify_slack_signature_valid(self):
        """Test valid Slack signature verification"""
        import time
        import hmac
        import hashlib
        
        # Create a mock request with valid signature
        timestamp = str(int(time.time()))
        body = '{"test": "data"}'
        signing_secret = "test_secret"
        
        sig_basestring = f"v0:{timestamp}:{body}"
        signature = "v0=" + hmac.new(
            signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Mock request object
        mock_request = MagicMock()
        mock_request.headers = {
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature
        }
        mock_request.body.return_value = body.encode()
        
        with patch.dict('os.environ', {'SLACK_SIGNING_SECRET': signing_secret}):
            result = verify_slack_signature(mock_request)
            assert result is True
    
    def test_verify_slack_signature_invalid(self):
        """Test invalid Slack signature verification"""
        mock_request = MagicMock()
        mock_request.headers = {
            "X-Slack-Request-Timestamp": "1234567890",
            "X-Slack-Signature": "v0=invalid_signature"
        }
        mock_request.body.return_value = b'{"test": "data"}'
        
        with patch.dict('os.environ', {'SLACK_SIGNING_SECRET': 'test_secret'}):
            result = verify_slack_signature(mock_request)
            assert result is False
    
    def test_verify_slack_signature_missing_headers(self):
        """Test signature verification with missing headers"""
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.body.return_value = b'{"test": "data"}'
        
        result = verify_slack_signature(mock_request)
        assert result is False
    
    def test_verify_slack_signature_old_timestamp(self):
        """Test signature verification with old timestamp"""
        import time
        
        old_timestamp = str(int(time.time()) - 400)  # 400 seconds ago
        
        mock_request = MagicMock()
        mock_request.headers = {
            "X-Slack-Request-Timestamp": old_timestamp,
            "X-Slack-Signature": "v0=test_signature"
        }
        mock_request.body.return_value = b'{"test": "data"}'
        
        with patch.dict('os.environ', {'SLACK_SIGNING_SECRET': 'test_secret'}):
            result = verify_slack_signature(mock_request)
            assert result is False
    
    def test_verify_slack_signature_no_secret(self):
        """Test signature verification when no secret is configured"""
        mock_request = MagicMock()
        mock_request.headers = {
            "X-Slack-Request-Timestamp": "1234567890",
            "X-Slack-Signature": "v0=test_signature"
        }
        mock_request.body.return_value = b'{"test": "data"}'
        
        with patch.dict('os.environ', {}, clear=True):
            result = verify_slack_signature(mock_request)
            assert result is True  # Should skip verification when no secret
    
    def test_store_qa_request_success(self):
        """Test successful Q&A request storage"""
        with patch('app.slack_app.get_db_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            
            _store_qa_request(
                installation_id=1,
                question="What is AI?",
                answer="AI is artificial intelligence.",
                citations='[{"title": "AI", "url": "https://example.com"}]',
                user_id="U123456",
                channel_id="C123456",
                thread_ts="1234567890.123456",
                conversation_id="conv_123"
            )
            
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()
    
    def test_store_qa_request_error(self):
        """Test Q&A request storage with error"""
        with patch('app.slack_app.get_db_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.add.side_effect = Exception("Database error")
            mock_get_session.return_value = mock_session
            
            # Should not raise exception
            _store_qa_request(
                installation_id=1,
                question="What is AI?",
                answer="AI is artificial intelligence.",
                citations='[]',
                user_id="U123456",
                channel_id="C123456"
            )
            
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()


class TestSlackHandlers:
    """Test Slack event handlers (these would require more complex mocking)"""
    
    @pytest.fixture
    def mock_installation(self):
        installation = MagicMock()
        installation.id = 1
        installation.team_id = "T123456"
        installation.team_name = "Test Team"
        installation.bot_user_id = "U123456"
        installation.is_active = True
        return installation
    
    def test_handle_ask_command_missing_installation(self):
        """Test /ask command when app not installed"""
        # This would require mocking the Slack Bolt framework
        # For now, just test the concept
        pass
    
    def test_handle_ask_command_empty_question(self):
        """Test /ask command with empty question"""
        # This would require mocking the Slack Bolt framework
        pass
    
    def test_handle_ask_command_success(self):
        """Test successful /ask command"""
        # This would require mocking the Slack Bolt framework
        pass
    
    def test_handle_app_mention_success(self):
        """Test successful app mention handling"""
        # This would require mocking the Slack Bolt framework
        pass
    
    def test_handle_direct_message_success(self):
        """Test successful direct message handling"""
        # This would require mocking the Slack Bolt framework
        pass
