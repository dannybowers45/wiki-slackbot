import os
import secrets
import httpx
from typing import Optional, Dict, Any
from urllib.parse import urlencode, parse_qs
from fastapi import HTTPException
from .models import Installation
from .db import get_db_session
from dotenv import load_dotenv

load_dotenv()

SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")


class SlackOAuth:
    def __init__(self):
        self.client_id = SLACK_CLIENT_ID
        self.client_secret = SLACK_CLIENT_SECRET
        self.base_url = APP_BASE_URL
        self.secret_key = SECRET_KEY
        
        if not self.client_id or not self.client_secret:
            raise ValueError("SLACK_CLIENT_ID and SLACK_CLIENT_SECRET must be set")
    
    def generate_oauth_url(self) -> tuple[str, str]:
        """Generate OAuth URL and state for Slack installation"""
        state = secrets.token_urlsafe(32)
        
        params = {
            "client_id": self.client_id,
            "scope": "commands chat:write app_mentions:read users:read team:read",
            "redirect_uri": f"{self.base_url}/oauth/callback",
            "state": state
        }
        
        oauth_url = f"https://slack.com/oauth/v2/authorize?{urlencode(params)}"
        return oauth_url, state
    
    async def handle_oauth_callback(
        self, 
        code: str, 
        state: str, 
        expected_state: str
    ) -> Dict[str, Any]:
        """Handle OAuth callback and exchange code for tokens"""
        
        # Verify state parameter
        if state != expected_state:
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        # Exchange code for tokens
        token_data = await self._exchange_code_for_tokens(code)
        
        # Get team information
        team_info = await self._get_team_info(token_data["access_token"])
        
        # Store installation in database
        installation = await self._store_installation(token_data, team_info)
        
        return {
            "success": True,
            "team_id": team_info["team"]["id"],
            "team_name": team_info["team"]["name"],
            "bot_user_id": token_data["bot_user_id"],
            "installation_id": installation.id
        }
    
    async def _exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """Exchange OAuth code for access tokens"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://slack.com/api/oauth.v2.access",
                data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": f"{self.base_url}/oauth/callback",
                },
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Failed to exchange code: {response.status_code}"
                )
            
            data = response.json()
            
            if not data.get("ok"):
                raise HTTPException(status_code=400, detail=f"OAuth error: {data.get('error')}")
            
            return data
    
    async def _get_team_info(self, access_token: str) -> Dict[str, Any]:
        """Get team information using access token"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://slack.com/api/team.info",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Failed to get team info: {response.status_code}"
                )
            
            data = response.json()
            
            if not data.get("ok"):
                raise HTTPException(
                    status_code=400, 
                    detail=f"Team info error: {data.get('error', 'Unknown error')}"
                )
            
            return data
    
    async def _store_installation(
        self, 
        token_data: Dict[str, Any], 
        team_info: Dict[str, Any]
    ) -> Installation:
        """Store installation data in database"""
        session = get_db_session()
        
        try:
            # Check if installation already exists
            existing = session.query(Installation).filter(
                Installation.team_id == team_info["team"]["id"]
            ).first()
            
            if existing:
                # Update existing installation
                existing.bot_token = token_data["access_token"]
                existing.access_token = token_data["access_token"]
                existing.scope = token_data.get("scope", "")
                existing.user_id = token_data.get("authed_user", {}).get("id", "")
                existing.is_active = True
                installation = existing
            else:
                # Create new installation
                installation = Installation(
                    team_id=team_info["team"]["id"],
                    team_name=team_info["team"]["name"],
                    bot_user_id=token_data["bot_user_id"],
                    bot_token=token_data["access_token"],
                    access_token=token_data["access_token"],
                    scope=token_data.get("scope", ""),
                    user_id=token_data.get("authed_user", {}).get("id", "")
                )
                session.add(installation)
            
            session.commit()
            session.refresh(installation)
            
            return installation
            
        except Exception as e:
            session.rollback()
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to store installation: {str(e)}"
            )
        finally:
            session.close()
    
    def get_installation_by_team_id(self, team_id: str) -> Optional[Installation]:
        """Get installation by team ID"""
        session = get_db_session()
        try:
            return session.query(Installation).filter(
                Installation.team_id == team_id,
                Installation.is_active == True
            ).first()
        finally:
            session.close()
    
    def deactivate_installation(self, team_id: str) -> bool:
        """Deactivate installation"""
        session = get_db_session()
        try:
            installation = session.query(Installation).filter(
                Installation.team_id == team_id
            ).first()
            
            if installation:
                installation.is_active = False
                session.commit()
                return True
            
            return False
            
        except Exception as e:
            session.rollback()
            return False
        finally:
            session.close()


# Global OAuth instance
slack_oauth = SlackOAuth()
