# Wikipedia Q&A Slackbot

A FastAPI web application with a Slack bot that answers questions using Wikipedia content with proper citations and supports multi-turn conversations.

## Features

- **Slack Integration**: OAuth flow for easy installation
- **Wikipedia Q&A**: Search and synthesize answers from Wikipedia
- **Citations**: All answers include clickable Wikipedia citations
- **Web Interface**: HTML interface for installation and logs
- **Database Logging**: All Q&A interactions stored with timestamps and viewable at <url>/logs 
- **Security**: Slack signature verification and OAuth state validation

## Quick Start

### Prerequisites

- Python 3.11+
- Slack App credentials

## Slack App Setup

### 1. Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click "Create New App" → "From scratch"
3. Enter app name: "Wikipedia Q&A Bot"
4. Select your workspace

### 2. Configure OAuth & Permissions

**Scopes (Bot Token Scopes):**
- `commands` - Add slash commands
- `chat:write` - Send messages
- `app_mentions:read` - Listen for mentions
- `users:read` - Get user information

**Redirect URLs:**
- Add: `https://<ngrok>/oauth/callback` (development)
- Add: `https://yourdomain.com/oauth/callback` (production)

### 3. Create Slash Command

1. Go to "Slash Commands" → "Create New Command"
2. Command: `/wiki`
3. Request URL: `https://<ngrok>/slack/commands`
4. Short Description: "Ask a question about any topic"
5. Usage Hint: "Wiki: What is machine learning?"

### 4. Enable Event Subscriptions

1. Go to "Event Subscriptions"
2. Enable Events: On
3. Request URL: `http://localhost:8000/slack/events`
4. Subscribe to bot events:
   - `app_mention`
   - `message.im`

### 5. Get Credentials

Copy these values to your `.env` file:
- **Bot User OAuth Token** → `SLACK_BOT_TOKEN`
- **Signing Secret** → `SLACK_SIGNING_SECRET`
- **Client ID** → `SLACK_CLIENT_ID`
- **Client Secret** → `SLACK_CLIENT_SECRET`

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd wikipedia-slackbot
   ```

2. **Install dependencies**
   ```bash
   make install
   # or
   pip install -r requirements.txt
   ```

4. **Setup environment**
   ```bash
   cp env.example .env
   # Edit .env with your necessary Slack app credentials
   ```

5. **Run the application**
   ```bash
   make dev
   # or
   uvicorn app.main:app --reload
   ```

6. **Visit the web interface**
   - Open https server
   - Click "Connect to Slack" to install the bot

## Configuration

### Environment Variables

```bash
# Slack App Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_CLIENT_ID=your-client-id
SLACK_CLIENT_SECRET=your-client-secret
SLACK_BOT_USER_ID=your-bot-user-id # optional fallback for local runs

# Wikipedia API
WIKIPEDIA_API_URL=https://en.wikipedia.org/api/rest_v1
```

## Usage

### Slack Commands

1. **Slash Command**: `/wiki What is machine learning?`
2. **Mention**: `@danny-wiki What is artificial intelligence?`

### Features

- **Citations**: All answers include Wikipedia sources with clickable links
- **Web Logs**: View all Q&A interactions at `/logs`

## API Endpoints

### Web Interface
- `GET /` - Home page with installation button
- `GET /install` - Start OAuth installation
- `GET /oauth/callback` - OAuth callback handler
- `GET /logs` - View Q&A logs
- `GET /health` - Health check

### API
- `GET /api/installations` - List all installations
- `GET /api/qa-requests` - List all Q&A requests

### Slack
- `POST /slack/events` - Slack event subscriptions
- `POST /slack/commands` - Slack slash commands
- `POST /slack/interactive` - Slack interactive components

## Development

### Project Structure

```
wikipedia-slackbot/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── slack_app.py         # Slack Bolt handlers
│   ├── wiki_client.py       # Wikipedia API client
│   ├── qa.py                # Q&A synthesis logic
│   ├── oauth.py             # Slack OAuth flow
│   ├── openai_client.py.    # LLM logic
│   ├── models.py            # Database models
│   ├── db.py                # Database connection
│   ├── templates/           # HTML templates
│   │   ├── index.html
│   │   └── logs.html
│   ├── static/              # Static files
│   └── tests/               # Test suite
├── requirements.txt
├── Makefile
└── README.md
```

### Commands

```bash
# Development
make dev          # Start development server
make test         # Run tests
make install      # Install dependencies
make clean        # Clean up files


### Testing

```bash
# Run all tests
pytest app/tests/ -v

# Run specific test file
pytest app/tests/test_wiki_client.py -v

# Run with coverage
pytest app/tests/ --cov=app --cov-report=html
```


**Production considerations**
   - Use HTTPS in production (place certs in `ssl/` for the nginx profile)
   - Move to a production database (e.g., PostgreSQL) and update `DATABASE_URL`
   - Configure logging/monitoring


## Architecture

### Components

1. **FastAPI Web App**: Handles OAuth, web interface, and API endpoints
2. **Slack Bot**: Processes commands, mentions, and DMs using Slack Bolt
3. **Wikipedia Client**: Searches and fetches content from Wikipedia API
4. **Q&A Service**: Synthesizes answers and manages conversation context
5. **Database**: SQLite for storing installations, Q&A logs, and conversation state

### Data Flow

1. User asks question in Slack
2. Slack sends event to `/slack/events` or `/slack/commands`
3. Bot verifies signature and processes request
4. Wikipedia client searches for relevant articles
5. Q&A service passes wikipedia information to openAI API which creates summary
6. Q&A appends links to summary
6. Response sent back to Slack
7. Q&A interaction logged to database



