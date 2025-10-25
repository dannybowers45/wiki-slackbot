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
    """Encapsulates the Slack OAuth flow and installation lifecycle management."""
    def __init__(self):
        """Load Slack credentials and base configuration from environment variables."""
        self.client_id = SLACK_CLIENT_ID
        self.client_secret = SLACK_CLIENT_SECRET
        self.base_url = APP_BASE_URL
        self.secret_key = SECRET_KEY
        
        if not self.client_id or not self.client_secret:
            raise ValueError("SLACK_CLIENT_ID and SLACK_CLIENT_SECRET must be set")
    
    def generate_oauth_url(self) -> tuple[str, str]:
        """
        Build the Slack installation URL alongside a one-time anti-CSRF state.

        Returns
            tuple[str, str]: Pair containing the OAuth URL for the "Add to Slack" button and the
                        random state token that must be echoed back during the callback.
        """
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
        """
        Complete the OAuth exchange and persist the resulting installation.

        Parameters
            code: Temporary authorization code supplied by Slack.
            state: State value returned by Slack, expected to match `expected_state`.
            expected_state: Value generated during `/install`; allows the caller to supply the
                            previously stored state token for validation.

        Returns
            Dict[str, Any]: Summary of the stored installation including team details and bot id.
        """
        
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
        """
        Swap a temporary authorization code for Slack bot and user tokens.

        Parameters
            code: Short-lived code provided by Slack after the user authorizes the app.

        Returns
            Dict[str, Any]: Raw response payload from Slack containing tokens, scopes, and user info.
        """
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
        """
        Retrieve metadata about the Slack workspace that installed the app.

        Parameters
            access_token: Access token returned by the OAuth exchange; required for the
                      `team.info` API call.

        Returns
            Dict[str, Any]: Team details (id, name) used for persistence and UI messaging.
        """
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
        """
        Persist or update the installation record in the database.

        Parameters
            token_data: Payload returned by Slack's OAuth exchange, containing bot tokens.
            team_info: Workspace metadata returned by `team.info`.

        Returns
            Installation: Newly created or updated SQLModel instance representing the install.
        """
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
        """
        Fetch an active installation for the given Slack workspace id.

        Parameters
            team_id: Slack workspace identifier supplied in the incoming event payload.

        Returns
            Optional[Installation]: Active installation when present, otherwise `None`.
        """
        session = get_db_session()
        try:
            return session.query(Installation).filter(
                Installation.team_id == team_id,
                Installation.is_active == True
            ).first()
        finally:
            session.close()
    
    def deactivate_installation(self, team_id: str) -> bool:
        """
        Soft-delete an installation when Slack reports the app was uninstalled.

        Parameters
            team_id:
                Workspace identifier received from Slack's `app_uninstalled` event.

        Returns
            bool: `True` when an installation was found and deactivated, `False` if no matching record exists.
        """
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
