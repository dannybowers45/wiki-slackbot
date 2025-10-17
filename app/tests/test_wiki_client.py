import pytest
import httpx
from unittest.mock import AsyncMock, patch
from app.wiki_client import WikipediaClient, WikipediaArticle, SearchResult


class TestWikipediaClient:
    @pytest.fixture
    def client(self):
        return WikipediaClient()
    
    @pytest.mark.asyncio
    async def test_search_success(self, client):
        """Test successful Wikipedia search"""
        mock_response_data = {
            "query": {
                "search": [
                    {
                        "title": "Machine Learning",
                        "snippet": "Machine learning is a subset of artificial intelligence...",
                        "pageid": 12345
                    },
                    {
                        "title": "Artificial Intelligence",
                        "snippet": "Artificial intelligence is intelligence demonstrated by machines...",
                        "pageid": 67890
                    }
                ]
            }
        }
        
        with patch.object(client.client, 'get') as mock_get:
            mock_response = AsyncMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            results = await client.search("machine learning", limit=2)
            
            assert len(results) == 2
            assert results[0].title == "Machine Learning"
            assert results[0].page_id == 12345
            assert "Machine learning is a subset" in results[0].snippet
            assert results[0].url == "https://en.wikipedia.org/wiki/Machine_Learning"
    
    @pytest.mark.asyncio
    async def test_search_empty_results(self, client):
        """Test search with no results"""
        mock_response_data = {"query": {"search": []}}
        
        with patch.object(client.client, 'get') as mock_get:
            mock_response = AsyncMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            results = await client.search("nonexistent topic")
            
            assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_search_error(self, client):
        """Test search with API error"""
        with patch.object(client.client, 'get') as mock_get:
            mock_get.side_effect = httpx.HTTPError("API Error")
            
            results = await client.search("test query")
            
            assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_get_article_success(self, client):
        """Test successful article retrieval"""
        mock_summary_data = {
            "title": "Machine Learning",
            "extract": "Machine learning is a subset of artificial intelligence...",
            "content_urls": {
                "desktop": {
                    "page": "https://en.wikipedia.org/wiki/Machine_learning"
                }
            },
            "pageid": 12345
        }
        
        mock_sections_data = {
            "sections": [
                {"title": "Overview"},
                {"title": "History"},
                {"title": "Applications"}
            ]
        }
        
        with patch.object(client.client, 'get') as mock_get:
            # Mock summary response
            mock_summary_response = AsyncMock()
            mock_summary_response.json.return_value = mock_summary_data
            mock_summary_response.raise_for_status.return_value = None
            
            # Mock sections response
            mock_sections_response = AsyncMock()
            mock_sections_response.json.return_value = mock_sections_data
            mock_sections_response.raise_for_status.return_value = None
            
            mock_get.side_effect = [mock_summary_response, mock_sections_response]
            
            article = await client.get_article("Machine Learning")
            
            assert article is not None
            assert article.title == "Machine Learning"
            assert article.page_id == 12345
            assert "Machine learning is a subset" in article.extract
            assert article.url == "https://en.wikipedia.org/wiki/Machine_learning"
            assert len(article.sections) == 3
            assert "Overview" in article.sections
    
    @pytest.mark.asyncio
    async def test_get_article_not_found(self, client):
        """Test article retrieval for non-existent article"""
        mock_response_data = {"error": "Not found"}
        
        with patch.object(client.client, 'get') as mock_get:
            mock_response = AsyncMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            article = await client.get_article("NonExistentArticle")
            
            assert article is None
    
    @pytest.mark.asyncio
    async def test_get_article_content_success(self, client):
        """Test getting full article content"""
        mock_response_data = {
            "query": {
                "pages": {
                    "12345": {
                        "extract": "Machine learning is a subset of artificial intelligence..."
                    }
                }
            }
        }
        
        with patch.object(client.client, 'get') as mock_get:
            mock_response = AsyncMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            content = await client.get_article_content("Machine Learning")
            
            assert content is not None
            assert "Machine learning is a subset" in content
    
    def test_clean_text(self, client):
        """Test text cleaning functionality"""
        dirty_text = "This is a test [1] with multiple   spaces and <b>HTML</b> tags."
        clean_text = client.clean_text(dirty_text)
        
        assert "[1]" not in clean_text
        assert "<b>" not in clean_text
        assert "</b>" not in clean_text
        assert "multiple   spaces" not in clean_text
        assert "multiple spaces" in clean_text
    
    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test client cleanup"""
        with patch.object(client.client, 'aclose') as mock_close:
            await client.close()
            mock_close.assert_called_once()
