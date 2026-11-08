"""
Unit tests for WebhookClient.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
import httpx

from app.infrastructure.adapters.webhook_client import WebhookClient


@pytest.mark.unit
class TestWebhookClient:
    """Test suite for WebhookClient"""

    def test_webhook_disabled_via_parameter(self):
        """Test webhook skips when enabled=False"""
        client = WebhookClient(enabled=False)
        result = client.notify_job_completion(123)
        assert result is False

    @patch('app.infrastructure.adapters.webhook_client.settings')
    def test_webhook_disabled_via_settings(self, mock_settings):
        """Test webhook skips when WEBHOOK_ENABLED=false in settings"""
        mock_settings.WEBHOOK_ENABLED = False
        mock_settings.WEBHOOK_URL = "http://test.com/webhook"

        client = WebhookClient()
        result = client.notify_job_completion(123)
        assert result is False

    @patch('app.infrastructure.adapters.webhook_client.settings')
    def test_webhook_missing_url(self, mock_settings):
        """Test webhook skips when WEBHOOK_URL not set"""
        mock_settings.WEBHOOK_URL = None
        mock_settings.WEBHOOK_API_KEY = "test-key"
        mock_settings.WEBHOOK_ENABLED = True

        client = WebhookClient()
        result = client.notify_job_completion(123)
        assert result is False

    @patch('app.infrastructure.adapters.webhook_client.settings')
    def test_webhook_missing_api_key(self, mock_settings):
        """Test webhook skips when WEBHOOK_API_KEY not set"""
        mock_settings.WEBHOOK_URL = "http://test.com/webhook"
        mock_settings.WEBHOOK_API_KEY = None
        mock_settings.WEBHOOK_ENABLED = True

        client = WebhookClient()
        result = client.notify_job_completion(123)
        assert result is False

    @patch('app.infrastructure.adapters.webhook_client.httpx.Client')
    def test_webhook_success(self, mock_client_class):
        """Test successful webhook call with API key"""
        # Mock response
        mock_response = Mock(status_code=200, text='{"success": true}')

        # Mock context manager
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        client = WebhookClient(webhook_url="http://test.com/webhook", api_key="test-api-key", enabled=True)
        result = client.notify_job_completion(123)

        assert result is True
        mock_client.post.assert_called_once_with(
            "http://test.com/webhook?jobId=123",
            headers={"X-API-Key": "test-api-key"}
        )

    @patch('app.infrastructure.adapters.webhook_client.httpx.Client')
    def test_webhook_retry_on_500(self, mock_client_class):
        """Test retry on 5xx server errors"""
        # Mock response
        mock_response = Mock(status_code=500, text='Internal Server Error')

        # Mock context manager
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        client = WebhookClient(webhook_url="http://test.com/webhook", api_key="test-api-key", enabled=True)
        result = client.notify_job_completion(123)

        assert result is False
        # Should retry 3 times
        assert mock_client.post.call_count == 3

    @patch('app.infrastructure.adapters.webhook_client.httpx.Client')
    def test_webhook_no_retry_on_401(self, mock_client_class):
        """Test no retry on 401 Unauthorized (invalid API key)"""
        # Mock response
        mock_response = Mock(status_code=401, text='Unauthorized: Invalid or missing API key')

        # Mock context manager
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        client = WebhookClient(webhook_url="http://test.com/webhook", api_key="wrong-api-key", enabled=True)
        result = client.notify_job_completion(123)

        assert result is False
        # Should NOT retry on 401 errors (authentication failure)
        assert mock_client.post.call_count == 1

    @patch('app.infrastructure.adapters.webhook_client.httpx.Client')
    def test_webhook_no_retry_on_404(self, mock_client_class):
        """Test no retry on 404 Not Found (job not found in backend)"""
        # Mock response
        mock_response = Mock(status_code=404, text='Job tidak ditemukan dengan ID: 123')

        # Mock context manager
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        client = WebhookClient(webhook_url="http://test.com/webhook", api_key="test-api-key", enabled=True)
        result = client.notify_job_completion(123)

        assert result is False
        # Should NOT retry on 404 errors (job not found)
        assert mock_client.post.call_count == 1

    @patch('app.infrastructure.adapters.webhook_client.httpx.Client')
    def test_webhook_no_retry_on_400(self, mock_client_class):
        """Test no retry on 400 Bad Request (job not in SUCCESS status)"""
        # Mock response
        mock_response = Mock(status_code=400, text='Job 123 is not in SUCCESS status')

        # Mock context manager
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        client = WebhookClient(webhook_url="http://test.com/webhook", api_key="test-api-key", enabled=True)
        result = client.notify_job_completion(123)

        assert result is False
        # Should NOT retry on 400 errors (invalid job status)
        assert mock_client.post.call_count == 1

    @patch('app.infrastructure.adapters.webhook_client.httpx.Client')
    def test_webhook_timeout_retry(self, mock_client_class):
        """Test retry on timeout exceptions"""
        # Mock context manager that raises timeout
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.TimeoutException("Request timeout")
        mock_client_class.return_value.__enter__.return_value = mock_client

        client = WebhookClient(webhook_url="http://test.com/webhook", api_key="test-api-key", enabled=True)
        result = client.notify_job_completion(123)

        assert result is False
        # Should retry 3 times on timeout
        assert mock_client.post.call_count == 3

    @patch('app.infrastructure.adapters.webhook_client.httpx.Client')
    def test_webhook_generic_exception_retry(self, mock_client_class):
        """Test retry on generic exceptions"""
        # Mock context manager that raises exception
        mock_client = MagicMock()
        mock_client.post.side_effect = Exception("Connection error")
        mock_client_class.return_value.__enter__.return_value = mock_client

        client = WebhookClient(webhook_url="http://test.com/webhook", api_key="test-api-key", enabled=True)
        result = client.notify_job_completion(123)

        assert result is False
        # Should retry 3 times on exception
        assert mock_client.post.call_count == 3

    @patch('app.infrastructure.adapters.webhook_client.httpx.Client')
    def test_webhook_eventual_success_after_retry(self, mock_client_class):
        """Test success after initial failures"""
        # Mock responses: fail twice, then succeed
        mock_responses = [
            Mock(status_code=503, text='Service Unavailable'),
            Mock(status_code=503, text='Service Unavailable'),
            Mock(status_code=200, text='{"success": true}')
        ]

        # Mock context manager
        mock_client = MagicMock()
        mock_client.post.side_effect = mock_responses
        mock_client_class.return_value.__enter__.return_value = mock_client

        client = WebhookClient(webhook_url="http://test.com/webhook", api_key="test-api-key", enabled=True)
        result = client.notify_job_completion(123)

        assert result is True
        assert mock_client.post.call_count == 3

    @patch('app.infrastructure.adapters.webhook_client.httpx.Client')
    def test_webhook_correct_url_format(self, mock_client_class):
        """Test webhook constructs correct URL with query parameter and API key header"""
        mock_response = Mock(status_code=200, text='OK')

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        client = WebhookClient(
            webhook_url="http://receiver.example.com/api/jobs/complete",
            api_key="secure-key-123",
            enabled=True
        )
        client.notify_job_completion(456)

        mock_client.post.assert_called_once_with(
            "http://receiver.example.com/api/jobs/complete?jobId=456",
            headers={"X-API-Key": "secure-key-123"}
        )

    def test_webhook_custom_timeout(self):
        """Test webhook uses correct timeout value"""
        client = WebhookClient(webhook_url="http://test.com/webhook", api_key="test-key", enabled=True)
        assert client.timeout == 30.0

    def test_webhook_max_retries(self):
        """Test webhook uses correct max retries"""
        client = WebhookClient(webhook_url="http://test.com/webhook", api_key="test-key", enabled=True)
        assert client.max_retries == 3

    @patch('app.infrastructure.adapters.webhook_client.time.sleep')
    @patch('app.infrastructure.adapters.webhook_client.httpx.Client')
    def test_webhook_exponential_backoff_on_500(self, mock_client_class, mock_sleep):
        """Test exponential backoff is applied on 5xx errors"""
        # Mock responses: 500, 500, 500 (all fail)
        mock_response = Mock(status_code=500, text='Internal Server Error')

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        client = WebhookClient(webhook_url="http://test.com/webhook", api_key="test-api-key", enabled=True)
        result = client.notify_job_completion(123)

        assert result is False
        assert mock_client.post.call_count == 3

        # Verify exponential backoff: 2^1=2s after 1st failure, 2^2=4s after 2nd failure
        expected_sleep_calls = [call(2), call(4)]
        assert mock_sleep.call_args_list == expected_sleep_calls

    @patch('app.infrastructure.adapters.webhook_client.time.sleep')
    @patch('app.infrastructure.adapters.webhook_client.httpx.Client')
    def test_webhook_exponential_backoff_on_timeout(self, mock_client_class, mock_sleep):
        """Test exponential backoff is applied on timeout exceptions"""
        # Mock timeout exceptions
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.TimeoutException("Request timeout")
        mock_client_class.return_value.__enter__.return_value = mock_client

        client = WebhookClient(webhook_url="http://test.com/webhook", api_key="test-api-key", enabled=True)
        result = client.notify_job_completion(123)

        assert result is False
        assert mock_client.post.call_count == 3

        # Verify exponential backoff: 2^1=2s, 2^2=4s
        expected_sleep_calls = [call(2), call(4)]
        assert mock_sleep.call_args_list == expected_sleep_calls

    @patch('app.infrastructure.adapters.webhook_client.time.sleep')
    @patch('app.infrastructure.adapters.webhook_client.httpx.Client')
    def test_webhook_no_backoff_on_success_after_retry(self, mock_client_class, mock_sleep):
        """Test backoff stops when request succeeds"""
        # Mock responses: 503, 200 (success on 2nd attempt)
        mock_responses = [
            Mock(status_code=503, text='Service Unavailable'),
            Mock(status_code=200, text='{"success": true}')
        ]

        mock_client = MagicMock()
        mock_client.post.side_effect = mock_responses
        mock_client_class.return_value.__enter__.return_value = mock_client

        client = WebhookClient(webhook_url="http://test.com/webhook", api_key="test-api-key", enabled=True)
        result = client.notify_job_completion(123)

        assert result is True
        assert mock_client.post.call_count == 2

        # Should only sleep once (2^1=2s) before 2nd attempt
        assert mock_sleep.call_args_list == [call(2)]

    @patch('app.infrastructure.adapters.webhook_client.time.sleep')
    @patch('app.infrastructure.adapters.webhook_client.httpx.Client')
    def test_webhook_no_backoff_on_4xx_errors(self, mock_client_class, mock_sleep):
        """Test no backoff on 4xx errors (no retry)"""
        # Mock 401 response (should not retry)
        mock_response = Mock(status_code=401, text='Unauthorized')

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        client = WebhookClient(webhook_url="http://test.com/webhook", api_key="wrong-key", enabled=True)
        result = client.notify_job_completion(123)

        assert result is False
        assert mock_client.post.call_count == 1

        # Should NOT sleep (no retry on 4xx)
        mock_sleep.assert_not_called()
