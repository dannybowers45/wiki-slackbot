import os
import secrets
from typing import List
from fastapi import FastAPI, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from .db import get_session, create_db_and_tables
from .models import QARequest, Installation, QARequestResponse, InstallationResponse
from .oauth import slack_oauth
from .slack_app import slack_events, slack_commands, slack_interactive
from dotenv import load_dotenv

load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="Wikipedia Q&A Slackbot",
    description="A Slack bot that answers questions using Wikipedia with citations",
    version="1.0.0"
)

# Create database tables on startup (Railway safe)
@app.on_event("startup")
async def on_startup():
    create_db_and_tables()

# Setup templates and static files
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Store OAuth states temporarily (in production, use Redis or database)
oauth_states = {}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Home page with Connect Slack button"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/install")
async def install():
    """Start OAuth installation process"""
    oauth_url, state = slack_oauth.generate_oauth_url()
    
    # Store state temporarily
    oauth_states[state] = True
    
    return RedirectResponse(url=oauth_url)


@app.get("/oauth/callback")
async def oauth_callback(
    code: str = None,
    state: str = None,
    error: str = None
):
    """Handle OAuth callback"""
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
    
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter")
    
    # Verify state
    if state not in oauth_states:
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    
    # Remove used state
    del oauth_states[state]
    
    try:
        result = await slack_oauth.handle_oauth_callback(code, state, state)
        
        return HTMLResponse(f"""
        <html>
            <head>
                <title>Installation Successful</title>
                <style>
                    body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
                    .success {{ background: #d4edda; border: 1px solid #c3e6cb; color: #155724; padding: 15px; border-radius: 5px; }}
                    .info {{ background: #d1ecf1; border: 1px solid #bee5eb; color: #0c5460; padding: 15px; border-radius: 5px; margin-top: 20px; }}
                </style>
            </head>
            <body>
                <div class="success">
                    <h2>Installation Successful!</h2>
                    <p>The Wikipedia Q&A Bot has been successfully installed in <strong>{result['team_name']}</strong>.</p>
                </div>
                <div class="info">
                    <h3>How to use:</h3>
                    <ul>
                        <li>Use the <code>/ask</code> command: <code>/ask What is machine learning?</code></li>
                        <li>Mention the bot: <code>@Wikipedia Q&A What is artificial intelligence?</code></li>
                        <li>Send a direct message to the bot</li>
                    </ul>
                    <p>The bot will search Wikipedia and provide answers with citations. You can ask follow-up questions in threads!</p>
                </div>
            </body>
        </html>
        """)
        
    except Exception as e:
        return HTMLResponse(f"""
        <html>
            <head>
                <title>Installation Failed</title>
                <style>
                    body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
                    .error {{ background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; padding: 15px; border-radius: 5px; }}
                </style>
            </head>
            <body>
                <div class="error">
                    <h2>Installation Failed</h2>
                    <p>Error: {str(e)}</p>
                    <p>Please try installing again or contact support.</p>
                </div>
            </body>
        </html>
        """)


@app.get("/logs", response_class=HTMLResponse)
async def logs(request: Request, session: Session = Depends(get_session)):
    """Display stored Q&A logs"""
    # Get all Q&A requests with installation info
    statement = select(QARequest, Installation).join(Installation)
    results = session.exec(statement).all()
    
    qa_logs = []
    for qa_request, installation in results:
        qa_logs.append({
            "id": qa_request.id,
            "question": qa_request.question,
            "answer": qa_request.answer,
            "citations": qa_request.citations,
            "user_id": qa_request.user_id,
            "channel_id": qa_request.channel_id,
            "thread_ts": qa_request.thread_ts,
            "conversation_id": qa_request.conversation_id,
            "created_at": qa_request.created_at,
            "team_name": installation.team_name
        })
    
    # Sort by creation date (newest first)
    qa_logs.sort(key=lambda x: x["created_at"], reverse=True)
    
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "qa_logs": qa_logs
    })


@app.get("/api/installations")
async def get_installations(session: Session = Depends(get_session)):
    """Get all installations (API endpoint)"""
    installations = session.exec(select(Installation)).all()
    return [InstallationResponse(
        id=inst.id,
        team_id=inst.team_id,
        team_name=inst.team_name,
        bot_user_id=inst.bot_user_id,
        is_active=inst.is_active,
        created_at=inst.created_at
    ) for inst in installations]


@app.get("/api/qa-requests")
async def get_qa_requests(session: Session = Depends(get_session)):
    """Get all Q&A requests (API endpoint)"""
    qa_requests = session.exec(select(QARequest)).all()
    return [QARequestResponse(
        id=qa.id,
        question=qa.question,
        answer=qa.answer,
        citations=qa.citations,
        user_id=qa.user_id,
        channel_id=qa.channel_id,
        thread_ts=qa.thread_ts,
        conversation_id=qa.conversation_id,
        created_at=qa.created_at
    ) for qa in qa_requests]


# Slack endpoints
app.post("/slack/events")(slack_events)
app.post("/slack/commands")(slack_commands)
app.post("/slack/interactive")(slack_interactive)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "wikipedia-slackbot"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
