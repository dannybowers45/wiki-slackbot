import json
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from .wiki_client import WikipediaClient, SearchResult, WikipediaArticle
from .models import ConversationState
from .db import get_db_session


@dataclass
class Citation:
    title: str
    url: str
    snippet: str
    page_id: int


@dataclass
class QAAnswer:
    answer: str
    citations: List[Citation]
    conversation_id: Optional[str] = None


class QAService:
    def __init__(self):
        self.wiki_client = WikipediaClient()
    
    async def answer_question(
        self, 
        question: str, 
        conversation_id: Optional[str] = None,
        installation_id: Optional[int] = None
    ) -> QAAnswer:
        """Generate an answer to a question using Wikipedia"""
        
        # Get conversation context if available
        context = await self._get_conversation_context(conversation_id, installation_id)
        
        # Search for relevant articles
        search_results = await self.wiki_client.search(question, limit=3)
        
        if not search_results:
            return QAAnswer(
                answer="I couldn't find any relevant information about that topic on Wikipedia. Could you try rephrasing your question?",
                citations=[],
                conversation_id=conversation_id
            )
        
        # Get detailed content from the most relevant articles
        articles = []
        citations = []
        
        for result in search_results[:2]:  # Limit to top 2 results
            article = await self.wiki_client.get_article(result.title)
            if article:
                articles.append(article)
                citations.append(Citation(
                    title=article.title,
                    url=article.url,
                    snippet=result.snippet,
                    page_id=article.page_id
                ))
        
        if not articles:
            return QAAnswer(
                answer="I found some search results but couldn't retrieve the detailed content. Please try asking a more specific question.",
                citations=[Citation(
                    title=result.title,
                    url=result.url,
                    snippet=result.snippet,
                    page_id=result.page_id
                ) for result in search_results[:2]],
                conversation_id=conversation_id
            )
        
        # Synthesize answer from articles
        answer = self._synthesize_answer(question, articles, context)
        
        # Update conversation context
        if conversation_id and installation_id:
            await self._update_conversation_context(
                conversation_id, 
                installation_id, 
                question, 
                answer.answer
            )
        
        return QAAnswer(
            answer=answer,
            citations=citations,
            conversation_id=conversation_id
        )
    
    def _synthesize_answer(
        self, 
        question: str, 
        articles: List[WikipediaArticle], 
        context: Optional[str] = None
    ) -> str:
        """Synthesize an answer from Wikipedia articles"""
        
        # Combine all article extracts
        combined_text = ""
        for article in articles:
            cleaned_extract = self.wiki_client.clean_text(article.extract)
            combined_text += f"\n\n{article.title}:\n{cleaned_extract}"
        
        # Simple answer synthesis - in a real implementation, you might use more sophisticated NLP
        # For now, we'll extract the most relevant sentences based on keywords from the question
        
        question_keywords = self._extract_keywords(question.lower())
        sentences = self._split_into_sentences(combined_text)
        
        # Score sentences based on keyword matches
        scored_sentences = []
        for sentence in sentences:
            score = self._score_sentence(sentence, question_keywords)
            if score > 0:
                scored_sentences.append((score, sentence))
        
        # Sort by score and take the best sentences
        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        
        # Build answer from top sentences
        answer_parts = []
        used_sentences = set()
        
        for score, sentence in scored_sentences[:5]:  # Limit to 5 sentences
            if sentence not in used_sentences and len(sentence.strip()) > 20:
                answer_parts.append(sentence.strip())
                used_sentences.add(sentence)
        
        if not answer_parts:
            # Fallback to first article's extract
            if articles:
                first_extract = self.wiki_client.clean_text(articles[0].extract)
                # Take first few sentences
                sentences = self._split_into_sentences(first_extract)
                answer_parts = sentences[:3]
        
        if not answer_parts:
            return "I found some information but couldn't generate a coherent answer. Please try asking a more specific question."
        
        # Join sentences and clean up
        answer = " ".join(answer_parts)
        answer = self.wiki_client.clean_text(answer)
        
        # Ensure answer isn't too long
        if len(answer) > 1000:
            answer = answer[:997] + "..."
        
        return answer
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        # Remove common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'what', 'when', 'where', 'why', 'how', 'who', 'which', 'that', 'this'
        }
        
        words = re.findall(r'\b\w+\b', text.lower())
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        return keywords
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _score_sentence(self, sentence: str, keywords: List[str]) -> int:
        """Score a sentence based on keyword matches"""
        sentence_lower = sentence.lower()
        score = 0
        for keyword in keywords:
            if keyword in sentence_lower:
                score += 1
        return score
    
    async def _get_conversation_context(
        self, 
        conversation_id: Optional[str], 
        installation_id: Optional[int]
    ) -> Optional[str]:
        """Get conversation context from database"""
        if not conversation_id or not installation_id:
            return None
        
        try:
            session = get_db_session()
            state = session.query(ConversationState).filter(
                ConversationState.conversation_id == conversation_id,
                ConversationState.installation_id == installation_id
            ).first()
            
            if state:
                context_data = json.loads(state.context)
                return context_data.get("last_answer", "")
            
            return None
            
        except Exception as e:
            print(f"Error getting conversation context: {e}")
            return None
        finally:
            session.close()
    
    async def _update_conversation_context(
        self, 
        conversation_id: str, 
        installation_id: int, 
        question: str, 
        answer: str
    ):
        """Update conversation context in database"""
        try:
            session = get_db_session()
            
            # Get or create conversation state
            state = session.query(ConversationState).filter(
                ConversationState.conversation_id == conversation_id,
                ConversationState.installation_id == installation_id
            ).first()
            
            context_data = {
                "last_question": question,
                "last_answer": answer,
                "conversation_count": 1
            }
            
            if state:
                # Update existing state
                existing_context = json.loads(state.context)
                context_data["conversation_count"] = existing_context.get("conversation_count", 0) + 1
                state.context = json.dumps(context_data)
                state.last_updated = datetime.utcnow()
            else:
                # Create new state
                state = ConversationState(
                    conversation_id=conversation_id,
                    installation_id=installation_id,
                    context=json.dumps(context_data)
                )
                session.add(state)
            
            session.commit()
            
        except Exception as e:
            print(f"Error updating conversation context: {e}")
            session.rollback()
        finally:
            session.close()
    
    def format_citations_for_slack(self, citations: List[Citation]) -> str:
        """Format citations for Slack display"""
        if not citations:
            return ""
        
        citation_text = "\n\n*Sources:*\n"
        for i, citation in enumerate(citations, 1):
            # Truncate snippet if too long
            snippet = citation.snippet
            if len(snippet) > 100:
                snippet = snippet[:97] + "..."
            
            citation_text += f"{i}. <{citation.url}|{citation.title}>\n"
            citation_text += f"   _{snippet}_\n"
        
        return citation_text
    
    async def close(self):
        """Close the Wikipedia client"""
        await self.wiki_client.close()


# Global QA service instance
qa_service = QAService()
