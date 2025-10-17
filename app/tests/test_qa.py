import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.qa import QAService, QAAnswer, Citation
from app.wiki_client import SearchResult, WikipediaArticle


class TestQAService:
    @pytest.fixture
    def qa_service(self):
        return QAService()
    
    @pytest.fixture
    def mock_search_results(self):
        return [
            SearchResult(
                title="Machine Learning",
                snippet="Machine learning is a subset of artificial intelligence...",
                url="https://en.wikipedia.org/wiki/Machine_Learning",
                page_id=12345
            ),
            SearchResult(
                title="Artificial Intelligence",
                snippet="Artificial intelligence is intelligence demonstrated by machines...",
                url="https://en.wikipedia.org/wiki/Artificial_Intelligence",
                page_id=67890
            )
        ]
    
    @pytest.fixture
    def mock_articles(self):
        return [
            WikipediaArticle(
                title="Machine Learning",
                extract="Machine learning is a subset of artificial intelligence that focuses on algorithms and statistical models.",
                url="https://en.wikipedia.org/wiki/Machine_Learning",
                page_id=12345,
                sections=["Overview", "History", "Applications"]
            ),
            WikipediaArticle(
                title="Artificial Intelligence",
                extract="Artificial intelligence is intelligence demonstrated by machines, in contrast to natural intelligence.",
                url="https://en.wikipedia.org/wiki/Artificial_Intelligence",
                page_id=67890,
                sections=["Definition", "History", "Applications"]
            )
        ]
    
    @pytest.mark.asyncio
    async def test_answer_question_success(self, qa_service, mock_search_results, mock_articles):
        """Test successful question answering"""
        with patch.object(qa_service.wiki_client, 'search', return_value=mock_search_results), \
             patch.object(qa_service.wiki_client, 'get_article', side_effect=mock_articles), \
             patch.object(qa_service, '_get_conversation_context', return_value=None), \
             patch.object(qa_service, '_update_conversation_context'):
            
            answer = await qa_service.answer_question("What is machine learning?")
            
            assert isinstance(answer, QAAnswer)
            assert len(answer.answer) > 0
            assert len(answer.citations) == 2
            assert answer.citations[0].title == "Machine Learning"
            assert answer.citations[1].title == "Artificial Intelligence"
    
    @pytest.mark.asyncio
    async def test_answer_question_no_results(self, qa_service):
        """Test question answering with no search results"""
        with patch.object(qa_service.wiki_client, 'search', return_value=[]):
            answer = await qa_service.answer_question("nonexistent topic")
            
            assert isinstance(answer, QAAnswer)
            assert "couldn't find any relevant information" in answer.answer
            assert len(answer.citations) == 0
    
    @pytest.mark.asyncio
    async def test_answer_question_no_articles(self, qa_service, mock_search_results):
        """Test question answering with search results but no articles"""
        with patch.object(qa_service.wiki_client, 'search', return_value=mock_search_results), \
             patch.object(qa_service.wiki_client, 'get_article', return_value=None):
            
            answer = await qa_service.answer_question("What is machine learning?")
            
            assert isinstance(answer, QAAnswer)
            assert "found some search results but couldn't retrieve" in answer.answer
            assert len(answer.citations) == 2  # Should still have search result citations
    
    def test_synthesize_answer(self, qa_service, mock_articles):
        """Test answer synthesis from articles"""
        question = "What is machine learning?"
        context = None
        
        answer = qa_service._synthesize_answer(question, mock_articles, context)
        
        assert len(answer) > 0
        assert "machine learning" in answer.lower() or "artificial intelligence" in answer.lower()
    
    def test_synthesize_answer_with_context(self, qa_service, mock_articles):
        """Test answer synthesis with conversation context"""
        question = "What are its applications?"
        context = "Machine learning is a subset of artificial intelligence."
        
        answer = qa_service._synthesize_answer(question, mock_articles, context)
        
        assert len(answer) > 0
    
    def test_extract_keywords(self, qa_service):
        """Test keyword extraction"""
        text = "What is machine learning and how does it work?"
        keywords = qa_service._extract_keywords(text)
        
        assert "machine" in keywords
        assert "learning" in keywords
        assert "work" in keywords
        assert "what" not in keywords  # Should be filtered out as stop word
        assert "is" not in keywords    # Should be filtered out as stop word
    
    def test_split_into_sentences(self, qa_service):
        """Test sentence splitting"""
        text = "This is sentence one. This is sentence two! This is sentence three?"
        sentences = qa_service._split_into_sentences(text)
        
        assert len(sentences) == 3
        assert "This is sentence one" in sentences[0]
        assert "This is sentence two" in sentences[1]
        assert "This is sentence three" in sentences[2]
    
    def test_score_sentence(self, qa_service):
        """Test sentence scoring based on keywords"""
        sentence = "Machine learning is a subset of artificial intelligence."
        keywords = ["machine", "learning", "artificial", "intelligence"]
        
        score = qa_service._score_sentence(sentence, keywords)
        
        assert score == 4  # All keywords should match
    
    def test_score_sentence_no_matches(self, qa_service):
        """Test sentence scoring with no keyword matches"""
        sentence = "This is about something completely different."
        keywords = ["machine", "learning"]
        
        score = qa_service._score_sentence(sentence, keywords)
        
        assert score == 0
    
    @pytest.mark.asyncio
    async def test_get_conversation_context_success(self, qa_service):
        """Test getting conversation context from database"""
        mock_state = MagicMock()
        mock_state.context = json.dumps({"last_answer": "Previous answer"})
        
        with patch('app.qa.get_db_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = mock_state
            mock_get_session.return_value = mock_session
            
            context = await qa_service._get_conversation_context("conv_123", 1)
            
            assert context == "Previous answer"
            mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_conversation_context_not_found(self, qa_service):
        """Test getting conversation context when not found"""
        with patch('app.qa.get_db_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = None
            mock_get_session.return_value = mock_session
            
            context = await qa_service._get_conversation_context("conv_123", 1)
            
            assert context is None
            mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_conversation_context_new(self, qa_service):
        """Test updating conversation context for new conversation"""
        with patch('app.qa.get_db_session') as mock_get_session, \
             patch('app.qa.ConversationState') as mock_state_class:
            
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = None
            mock_get_session.return_value = mock_session
            
            mock_state = MagicMock()
            mock_state_class.return_value = mock_state
            
            await qa_service._update_conversation_context("conv_123", 1, "What is AI?", "AI is...")
            
            mock_session.add.assert_called_once_with(mock_state)
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_conversation_context_existing(self, qa_service):
        """Test updating conversation context for existing conversation"""
        mock_state = MagicMock()
        mock_state.context = json.dumps({"conversation_count": 1})
        
        with patch('app.qa.get_db_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = mock_state
            mock_get_session.return_value = mock_session
            
            await qa_service._update_conversation_context("conv_123", 1, "What is AI?", "AI is...")
            
            mock_session.add.assert_not_called()  # Should not add new state
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()
    
    def test_format_citations_for_slack(self, qa_service):
        """Test formatting citations for Slack"""
        citations = [
            Citation(
                title="Machine Learning",
                url="https://en.wikipedia.org/wiki/Machine_Learning",
                snippet="Machine learning is a subset of artificial intelligence...",
                page_id=12345
            ),
            Citation(
                title="Artificial Intelligence",
                url="https://en.wikipedia.org/wiki/Artificial_Intelligence",
                snippet="Artificial intelligence is intelligence demonstrated by machines...",
                page_id=67890
            )
        ]
        
        formatted = qa_service.format_citations_for_slack(citations)
        
        assert "*Sources:*" in formatted
        assert "Machine Learning" in formatted
        assert "Artificial Intelligence" in formatted
        assert "https://en.wikipedia.org/wiki/Machine_Learning" in formatted
        assert "https://en.wikipedia.org/wiki/Artificial_Intelligence" in formatted
    
    def test_format_citations_for_slack_empty(self, qa_service):
        """Test formatting empty citations for Slack"""
        formatted = qa_service.format_citations_for_slack([])
        
        assert formatted == ""
    
    @pytest.mark.asyncio
    async def test_close(self, qa_service):
        """Test QA service cleanup"""
        with patch.object(qa_service.wiki_client, 'close') as mock_close:
            await qa_service.close()
            mock_close.assert_called_once()
