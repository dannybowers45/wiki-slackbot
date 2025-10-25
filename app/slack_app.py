import os
import re
import json
import hashlib
import hmac
import time
import asyncio
from typing import Optional
from fastapi import Request, HTTPException
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.authorization import AuthorizeResult
from slack_sdk.errors import SlackApiError
from .models import QARequest
from .db import get_db_session
from .qa import qa_service
from .oauth import slack_oauth
from dotenv import load_dotenv

load_dotenv()

SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_BOT_USER_ID = os.getenv("SLACK_BOT_USER_ID")


async def authorize(enterprise_id, team_id, logger, **kwargs) -> Optional[AuthorizeResult]:
    """
    Resolve OAuth credentials for the workspace making a Slack API call.

    Parameters
        enterprise_id:
            Slack enterprise grid id when present (unused but part of the contract).
        team_id:
            Workspace identifier used to locate the stored installation.
        logger:
            Bolt logger which we use for verbose diagnostics.
        **kwargs:
            Additional values supplied by Bolt (not used).

    Returns
        Optional[AuthorizeResult]
            Returns an `AuthorizeResult` populated with the correct bot token and user
            id when we locate a matching installation, or falls back to environment
            variables for local development. `None` signals Bolt to reject the request.

    """
    installation = slack_oauth.get_installation_by_team_id(team_id)
    if installation:
        return AuthorizeResult(
            enterprise_id=enterprise_id,
            team_id=team_id,
            bot_token=installation.bot_token,
            bot_user_id=installation.bot_user_id,
        )

    if SLACK_BOT_TOKEN:
        if logger:
            logger.debug(f"Falling back to env bot token for team {team_id}")
        return AuthorizeResult(
            enterprise_id=enterprise_id,
            team_id=team_id,
            bot_token=SLACK_BOT_TOKEN,
            bot_user_id=SLACK_BOT_USER_ID,
        )

    if logger:
        logger.error(f"No active installation found for team {team_id}")
    return None

# Initialize Slack app
app = AsyncApp(
    signing_secret=SLACK_SIGNING_SECRET,
    process_before_response=False,
    authorize=authorize
)

# Create request handler
handler = AsyncSlackRequestHandler(app)


async def verify_slack_signature(request: Request) -> bool:
    """
    Validate that an inbound HTTP request truly originated from Slack.

    Parameters
        request: The incoming FastAPI request containing Slack headers and body payload.
    
    Returns
        bool: `True` when the signature and timestamp checks pass, `False` otherwise.

    We recompute the expected HMAC (hash based message authentication code) using the configured signing secret and reject
    replayed requests that fall outside a five-minute tolerance window. This
    mirrors Slack's official verification recipe to guard against spoofed events.
    """
    if not SLACK_SIGNING_SECRET:
        return True
    
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    
    if not timestamp or not signature:
        return False
    
    # Check timestamp (prevent replay attacks)
    if abs(time.time() - int(timestamp)) > 60 * 5:  # 5 minutes
        return False
    
    # Verify signature
    body_bytes = await request.body()
    sig_basestring = b"v0:" + timestamp.encode() + b":" + body_bytes
    
    # Calculate the expected signature
    expected_signature = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        sig_basestring,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)


@app.command("/wiki")
async def handle_wiki_command(ack, body, client, logger):
    """
    Process the `/wiki` slash command end to end.

    Workflow
    1. Acknowledge the command immediately to satisfy Slack's 3 second SLA.
    2. Resolve the installation to obtain a bot token scoped to the workspace.
    3. Validate that the user provided text, derive a conversation id, and hand
       the question to the QA service.
    4. Post the synthesized answer (complete with citations) back to the channel.
    5. Persist the full interaction for later analytics via `_store_qa_request`.

    """
    try:
        await ack(
            response_type="ephemeral",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": ":hourglass_flowing_sand: *Working on it...* I'm pulling fresh details from Wikipedia."
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "You'll see the full answer here in just a moment."
                        }
                    ]
                }
            ],
            text="Fetching the latest info from Wikipedia..."
        )
    except SlackApiError as exc:
        if logger:
            logger.warning("Failed to send rich ack for /wiki command: %s", exc)
        await ack(text="Working on it...")
    except Exception as exc:
        if logger:
            logger.warning("Unexpected error acknowledging /wiki command: %s", exc)
        await ack(text="Working on it...")
    
    try:
        team_id = body["team_id"]
        installation = slack_oauth.get_installation_by_team_id(team_id)
        
        if not installation:
            await client.chat_postMessage(
                channel=body["channel_id"],
                text="This app hasn't been properly installed. Please reinstall the app."
            )
            return
        
        # Get question from command
        question = body.get("text", "").strip()
        
        if not question:
            await client.chat_postMessage(
                channel=body["channel_id"],
                text="Please provide a question. Usage: `/wiki What is machine learning?`"
            )
            return
        
        # Generate conversation ID for this channel
        conversation_id = f"{team_id}_{body['channel_id']}"
        
        # Get answer from QA service
        answer = await qa_service.answer_question(
            question=question,
            conversation_id=conversation_id,
            installation_id=installation.id
        )
        
        # Format response with citations
        response_text = answer.answer
        if answer.citations:
            response_text += qa_service.format_citations_for_slack(answer.citations)
        
        # Post response
        await client.chat_postMessage(
            channel=body["channel_id"],
            text=response_text,
            thread_ts=None  # Post as new message, not in thread
        )
        
        # Store Q&A in database
        await _store_qa_request(
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
        logger.error(f"Error handling /wiki command: {e}")
        await client.chat_postMessage(
            channel=body["channel_id"],
            text="Sorry, I encountered an error while processing your question. Please try again."
        )


@app.event("app_mention")
async def handle_app_mention(event, client, logger):
    """
    Respond to channel messages that directly mention the bot.

    The handler strips the mention component from the Slack text, treats the
    remainder as a user question, and reuses the same QA pipeline as the slash
    command. Answers are posted in-thread to keep conversations tidy.

    Parameters
    ----------
    event:
        Raw Slack event payload containing user, channel, and text information.
    client:
        Slack WebClient bound to the workspace-scoped bot token.
    logger:
        Logger provided by Bolt for structured diagnostics.
    """

    try:
        # Get installation
        team_id = event["team"]
        installation = slack_oauth.get_installation_by_team_id(team_id)
        
        if not installation:
            return  # Silently ignore if not installed
        
        # Extract question from mention
        text = event.get("text", "")
        mention_pattern = r"<@.*?>"
        question = re.sub(mention_pattern, "", text).strip()

        if not question:
            await client.chat_postMessage(
                channel=event["channel"],
                text="Hi! Ask me anything and I'll search Wikipedia for you. Try: `What is artificial intelligence?`"
            )
            return
        
        # Generate conversation ID
        conversation_id = f"{team_id}_{event['channel']}"
        
        # Get answer
        answer = await qa_service.answer_question(
            question=question,
            conversation_id=conversation_id,
            installation_id=installation.id
        )
        
        # Format and post response
        response_text = answer.answer
        if answer.citations:
            response_text += qa_service.format_citations_for_slack(answer.citations)
        
        await client.chat_postMessage(
            channel=event["channel"],
            text=response_text,
            thread_ts=event.get("ts")  # Reply in thread
        )
        
        # Store Q&A
        await _store_qa_request(
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
async def handle_direct_message(event, client, logger):
    """
    Deliver answers for direct messages in Slack.

    We only react to 1:1 conversations (channel_type == "im") and ignore messages
    emitted by bots to prevent feedback loops. A unique conversation id including
    the user id is generated so the QA service can maintain private context and
    memory per direct message thread.
    """
    try:
        if event.get("channel_type") != "im":
            return

        team_id = event.get("team")
        if not team_id:
            return

        installation = slack_oauth.get_installation_by_team_id(team_id)
        if not installation:
            return

        if event.get("bot_id"):
            return

        question = event.get("text", "").strip()
        if not question:
            await client.chat_postMessage(
                channel=event["channel"],
                text="Hi! Ask me anything and I'll search Wikipedia for you. Try: `What is machine learning?`"
            )
            return

        conversation_id = f"{team_id}_{event['channel']}_{event['user']}"
        answer = await qa_service.answer_question(
            question=question,
            conversation_id=conversation_id,
            installation_id=installation.id
        )

        response_text = answer.answer
        if answer.citations:
            response_text += qa_service.format_citations_for_slack(answer.citations)

        await client.chat_postMessage(
            channel=event["channel"],
            text=response_text
        )

        await _store_qa_request(
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
    except Exception as exc:
        logger.error(f"Error handling DM: {exc}")


async def _store_qa_request(
    installation_id: int,
    question: str,
    answer: str,
    citations: str,
    user_id: str,
    channel_id: str,
    thread_ts: Optional[str] = None,
    conversation_id: Optional[str] = None
):
    """
    Persist a completed Q&A exchange to the database.

    Parameters
        installation_id:
            Foreign key tying the interaction back to the Slack workspace.
        question:
            Raw question text received from the Slack user.
        answer:
            Formatted answer generated by the QA service.
        citations:
            JSON-encoded list of citation metadata appended to the response.
        user_id:
            Slack user identifier who asked the question.
        channel_id:
            Channel or DM id where the conversation took place.
        thread_ts:
            Optional thread timestamp when the answer was delivered in-thread.
        conversation_id:
            Stable identifier used by the QA service to store/resume context.

    Database operations are executed inside a background thread via
    `asyncio.to_thread` so the async Slack handlers remain non-blocking.
    """

    def _persist():
        """Write the QARequest record using a synchronous SQLModel session."""
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
        except Exception as exc:
            print(f"Error storing QA request: {exc}")
            session.rollback()
        finally:
            session.close()

    await asyncio.to_thread(_persist)


# FastAPI endpoints for Slack
async def slack_events(request: Request):
    """
    FastAPI entry point for Slack event subscriptions.

    The function validates the signature and delegates the heavy lifting to Bolt's
    request handler. Any invalid signature results in a 400 error so Slack can
    retry or mark the request as failed.
    """
    if not await verify_slack_signature(request):
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    return await handler.handle(request)


async def slack_commands(request: Request):
    """
    FastAPI bridge for Slack slash command invocations.

    Identical to `slack_events` but dedicated to `/commands` traffic so the routing
    in `app.main` stays explicit and maintainable.
    """
    if not await verify_slack_signature(request):
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    return await handler.handle(request)


async def slack_interactive(request: Request):
    """
    FastAPI bridge for interactive payloads (buttons, select menus, modals).

    Even though the current app does not register interactive handlers, we keep
    the endpoint wired so future UX improvements only require adding Bolt listeners.
    """
    if not await verify_slack_signature(request):
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    return await handler.handle(request)
