import os
import json
import hashlib
import hmac
import time
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException
from slack_bolt import App
from slack_bolt.adapter.fastapi import SlackRequestHandler
from .models import QARequest, Installation
from .db import get_db_session
from .qa import qa_service
from .oauth import slack_oauth
from dotenv import load_dotenv

load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

# Initialize Slack app
app = App(
    token=SLACK_BOT_TOKEN,
    signing_secret=SLACK_SIGNING_SECRET,
    process_before_response=True
)

# Create request handler
handler = SlackRequestHandler(app)


def verify_slack_signature(request: Request) -> bool:
    """Verify Slack request signature"""
    if not SLACK_SIGNING_SECRET:
        return True  # Skip verification in development
    
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    
    if not timestamp or not signature:
        return False
    
    # Check timestamp (prevent replay attacks)
    if abs(time.time() - int(timestamp)) > 60 * 5:  # 5 minutes
        return False
    
    # Verify signature
    body = request.body()
    if isinstance(body, bytes):
        body = body.decode('utf-8')
    
    sig_basestring = f"v0:{timestamp}:{body}"
    expected_signature = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)


@app.command("/ask")
def handle_ask_command(ack, body, client, logger):
    """Handle /ask slash command"""
    ack()
    
    try:
        # Get installation
        team_id = body["team_id"]
        installation = slack_oauth.get_installation_by_team_id(team_id)
        
        if not installation:
            client.chat_postMessage(
                channel=body["channel_id"],
                text="❌ This app hasn't been properly installed. Please reinstall the app."
            )
            return
        
        # Get question from command
        question = body.get("text", "").strip()
        
        if not question:
            client.chat_postMessage(
                channel=body["channel_id"],
                text="❓ Please provide a question. Usage: `/ask What is machine learning?`"
            )
            return
        
        # Generate conversation ID for this channel
        conversation_id = f"{team_id}_{body['channel_id']}"
        
        # Get answer from QA service
        import asyncio
        answer = asyncio.run(qa_service.answer_question(
            question=question,
            conversation_id=conversation_id,
            installation_id=installation.id
        ))
        
        # Format response with citations
        response_text = answer.answer
        if answer.citations:
            response_text += qa_service.format_citations_for_slack(answer.citations)
        
        # Post response
        client.chat_postMessage(
            channel=body["channel_id"],
            text=response_text,
            thread_ts=None  # Post as new message, not in thread
        )
        
        # Store Q&A in database
        _store_qa_request(
            installation_id=installation.id,
            question=question,
            answer=answer.answer,
            citations=json.dumps([{
                "title": c.title,
                "url": c.url,
                "snippet": c.snippet,
                "page_id": c.page_id
            } for c in answer.citations]),
            user_id=body["user_id"],
            channel_id=body["channel_id"],
            conversation_id=conversation_id
        )
        
    except Exception as e:
        logger.error(f"Error handling /ask command: {e}")
        client.chat_postMessage(
            channel=body["channel_id"],
            text="❌ Sorry, I encountered an error while processing your question. Please try again."
        )


@app.event("app_mention")
def handle_app_mention(event, client, logger):
    """Handle app mentions"""
    try:
        # Get installation
        team_id = event["team"]
        installation = slack_oauth.get_installation_by_team_id(team_id)
        
        if not installation:
            return  # Silently ignore if not installed
        
        # Extract question from mention
        text = event.get("text", "")
        # Remove the mention part
        question = text.replace(f"<@{event.get('bot_id', '')}>", "").strip()
        
        if not question:
            client.chat_postMessage(
                channel=event["channel"],
                text="👋 Hi! Ask me anything and I'll search Wikipedia for you. Try: `What is artificial intelligence?`"
            )
            return
        
        # Generate conversation ID
        conversation_id = f"{team_id}_{event['channel']}"
        
        # Get answer
        import asyncio
        answer = asyncio.run(qa_service.answer_question(
            question=question,
            conversation_id=conversation_id,
            installation_id=installation.id
        ))
        
        # Format and post response
        response_text = answer.answer
        if answer.citations:
            response_text += qa_service.format_citations_for_slack(answer.citations)
        
        client.chat_postMessage(
            channel=event["channel"],
            text=response_text,
            thread_ts=event.get("ts")  # Reply in thread
        )
        
        # Store Q&A
        _store_qa_request(
            installation_id=installation.id,
            question=question,
            answer=answer.answer,
            citations=json.dumps([{
                "title": c.title,
                "url": c.url,
                "snippet": c.snippet,
                "page_id": c.page_id
            } for c in answer.citations]),
            user_id=event["user"],
            channel_id=event["channel"],
            thread_ts=event.get("ts"),
            conversation_id=conversation_id
        )
        
    except Exception as e:
        logger.error(f"Error handling app mention: {e}")


@app.event("message")
def handle_direct_message(event, client, logger):
    """Handle direct messages"""
    try:
        # Only handle DMs (not channel messages)
        if event.get("channel_type") != "im":
            return
        
        # Get installation
        team_id = event["team"]
        installation = slack_oauth.get_installation_by_team_id(team_id)
        
        if not installation:
            return
        
        # Skip bot messages
        if event.get("bot_id"):
            return
        
        # Get question from message
        question = event.get("text", "").strip()
        
        if not question:
            client.chat_postMessage(
                channel=event["channel"],
                text="👋 Hi! Ask me anything and I'll search Wikipedia for you. Try: `What is machine learning?`"
            )
            return
        
        # Generate conversation ID for DM
        conversation_id = f"{team_id}_{event['channel']}_{event['user']}"
        
        # Get answer
        import asyncio
        answer = asyncio.run(qa_service.answer_question(
            question=question,
            conversation_id=conversation_id,
            installation_id=installation.id
        ))
        
        # Format and post response
        response_text = answer.answer
        if answer.citations:
            response_text += qa_service.format_citations_for_slack(answer.citations)
        
        client.chat_postMessage(
            channel=event["channel"],
            text=response_text
        )
        
        # Store Q&A
        _store_qa_request(
            installation_id=installation.id,
            question=question,
            answer=answer.answer,
            citations=json.dumps([{
                "title": c.title,
                "url": c.url,
                "snippet": c.snippet,
                "page_id": c.page_id
            } for c in answer.citations]),
            user_id=event["user"],
            channel_id=event["channel"],
            conversation_id=conversation_id
        )
        
    except Exception as e:
        logger.error(f"Error handling DM: {e}")


def _store_qa_request(
    installation_id: int,
    question: str,
    answer: str,
    citations: str,
    user_id: str,
    channel_id: str,
    thread_ts: Optional[str] = None,
    conversation_id: Optional[str] = None
):
    """Store Q&A request in database"""
    session = get_db_session()
    try:
        qa_request = QARequest(
            installation_id=installation_id,
            question=question,
            answer=answer,
            citations=citations,
            user_id=user_id,
            channel_id=channel_id,
            thread_ts=thread_ts,
            conversation_id=conversation_id
        )
        session.add(qa_request)
        session.commit()
    except Exception as e:
        print(f"Error storing QA request: {e}")
        session.rollback()
    finally:
        session.close()


# FastAPI endpoints for Slack
async def slack_events(request: Request):
    """Handle Slack events"""
    if not verify_slack_signature(request):
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    return await handler.handle(request)


async def slack_commands(request: Request):
    """Handle Slack commands"""
    if not verify_slack_signature(request):
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    return await handler.handle(request)


async def slack_interactive(request: Request):
    """Handle Slack interactive components"""
    if not verify_slack_signature(request):
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    return await handler.handle(request)
