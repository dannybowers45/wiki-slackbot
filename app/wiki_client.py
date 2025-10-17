import httpx
import json
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

WIKIPEDIA_API_URL = os.getenv("WIKIPEDIA_API_URL", "https://en.wikipedia.org/api/rest_v1")


@dataclass
class WikipediaArticle:
    title: str
    extract: str
    url: str
    page_id: int
    sections: List[str] = None


@dataclass
class SearchResult:
    title: str
    snippet: str
    url: str
    page_id: int


class WikipediaClient:
    def __init__(self):
        self.base_url = WIKIPEDIA_API_URL
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def search(self, query: str, limit: int = 5) -> List[SearchResult]:
        """Search Wikipedia for articles matching the query"""
        try:
            # Use the search API
            search_url = f"https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
                "srprop": "snippet"
            }
            
            response = await self.client.get(search_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get("query", {}).get("search", []):
                results.append(SearchResult(
                    title=item["title"],
                    snippet=item["snippet"],
                    url=f"https://en.wikipedia.org/wiki/{item['title'].replace(' ', '_')}",
                    page_id=item["pageid"]
                ))
            
            return results
            
        except Exception as e:
            print(f"Error searching Wikipedia: {e}")
            return []
    
    async def get_article(self, title: str) -> Optional[WikipediaArticle]:
        """Get full article content by title"""
        try:
            # Get article extract
            extract_url = f"{self.base_url}/page/summary/{title.replace(' ', '_')}"
            response = await self.client.get(extract_url)
            response.raise_for_status()
            data = response.json()
            
            if "extract" not in data:
                return None
            
            # Get article sections for better context
            sections = await self._get_article_sections(title)
            
            return WikipediaArticle(
                title=data["title"],
                extract=data["extract"],
                url=data["content_urls"]["desktop"]["page"],
                page_id=data["pageid"],
                sections=sections
            )
            
        except Exception as e:
            print(f"Error getting Wikipedia article: {e}")
            return None
    
    async def _get_article_sections(self, title: str) -> List[str]:
        """Get article sections for better context"""
        try:
            sections_url = f"{self.base_url}/page/sections/{title.replace(' ', '_')}"
            response = await self.client.get(sections_url)
            response.raise_for_status()
            data = response.json()
            
            return [section["title"] for section in data.get("sections", [])]
            
        except Exception:
            return []
    
    async def get_article_content(self, title: str) -> Optional[str]:
        """Get full article content as plain text"""
        try:
            # Use the MediaWiki API to get full content
            content_url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "format": "json",
                "titles": title,
                "prop": "extracts",
                "exintro": False,
                "explaintext": True,
                "exsectionformat": "plain"
            }
            
            response = await self.client.get(content_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            pages = data.get("query", {}).get("pages", {})
            for page_id, page_data in pages.items():
                if page_id != "-1":  # Page exists
                    return page_data.get("extract", "")
            
            return None
            
        except Exception as e:
            print(f"Error getting article content: {e}")
            return None
    
    def clean_text(self, text: str) -> str:
        """Clean Wikipedia text by removing references and formatting"""
        # Remove reference markers like [1], [2], etc.
        text = re.sub(r'\[\d+\]', '', text)
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text)
        # Remove HTML tags if any
        text = re.sub(r'<[^>]+>', '', text)
        return text.strip()
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


# Global client instance
wiki_client = WikipediaClient()
