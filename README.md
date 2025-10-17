# Wikipedia Q&A Slackbot

A FastAPI web application with a Slack bot that answers questions using Wikipedia content with proper citations and supports multi-turn conversations.

## Features

- **Slack Integration**: OAuth flow for easy installation
- **Wikipedia Q&A**: Search and synthesize answers from Wikipedia
- **Citations**: All answers include clickable Wikipedia citations
- **Multi-turn Conversations**: Follow-up questions in threads with context
- **Web Interface**: Beautiful HTML interface for installation and logs
- **Database Logging**: All Q&A interactions stored with timestamps
- **Security**: Slack signature verification and OAuth state validation
- **Docker Support**: Easy deployment with Docker and docker-compose

## Quick Start

### Prerequisites

- Python 3.11+
- Slack App credentials
- Docker (optional)

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

3. **Setup environment**
   ```bash
   cp env.example .env
   # Edit .env with your Slack app credentials
   ```

4. **Run the application**
   ```bash
   make dev
   # or
   uvicorn app.main:app --reload
   ```

5. **Visit the web interface**
   - Open http://localhost:8000
   - Click "Connect to Slack" to install the bot

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
- `im:history` - Read direct messages
- `users:read` - Get user information

**Redirect URLs:**
- Add: `http://localhost:8000/oauth/callback` (development)
- Add: `https://yourdomain.com/oauth/callback` (production)

### 3. Create Slash Command

1. Go to "Slash Commands" → "Create New Command"
2. Command: `/ask`
3. Request URL: `http://localhost:8000/slack/commands`
4. Short Description: "Ask a question about any topic"
5. Usage Hint: "What is machine learning?"

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

## Configuration

### Environment Variables

```bash
# Slack App Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_CLIENT_ID=your-client-id
SLACK_CLIENT_SECRET=your-client-secret

# App Configuration
APP_BASE_URL=http://localhost:8000
SECRET_KEY=your-secret-key-for-oauth-state

# Database
DATABASE_URL=sqlite:///./wikipedia_bot.db

# Wikipedia API
WIKIPEDIA_API_URL=https://en.wikipedia.org/api/rest_v1
```

## Usage

### Slack Commands

1. **Slash Command**: `/ask What is machine learning?`
2. **Mention**: `@Wikipedia Q&A What is artificial intelligence?`
3. **Direct Message**: Send a message directly to the bot

### Features

- **Citations**: All answers include Wikipedia sources with clickable links
- **Thread Context**: Ask follow-up questions in threads for context-aware responses
- **Multi-turn Conversations**: The bot remembers conversation context
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
│   ├── models.py            # Database models
│   ├── db.py                # Database connection
│   ├── templates/           # HTML templates
│   │   ├── index.html
│   │   └── logs.html
│   ├── static/              # Static files
│   └── tests/               # Test suite
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── slack_app_manifest.yaml
└── README.md
```

### Commands

```bash
# Development
make dev          # Start development server
make test         # Run tests
make install      # Install dependencies
make clean        # Clean up files

# Docker
make docker-build # Build Docker image
make docker-up    # Start with docker-compose
```

### Testing

```bash
# Run all tests
pytest app/tests/ -v

# Run specific test file
pytest app/tests/test_wiki_client.py -v

# Run with coverage
pytest app/tests/ --cov=app --cov-report=html
```

## Deployment

### Docker Deployment

1. **Build and run with Docker Compose**
   ```bash
   docker-compose up -d
   ```

2. **Environment setup**
   ```bash
   # Copy and edit environment file
   cp env.example .env
   # Update with production values
   ```

3. **Production considerations**
   - Use HTTPS in production
   - Set up proper SSL certificates
   - Use a production database (PostgreSQL)
   - Configure proper logging
   - Set up monitoring and alerts

### Manual Deployment

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables**
   ```bash
   export SLACK_BOT_TOKEN="your-token"
   export SLACK_SIGNING_SECRET="your-secret"
   # ... other variables
   ```

3. **Run the application**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

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
5. Q&A service synthesizes answer with citations
6. Response sent back to Slack
7. Q&A interaction logged to database

### Security

- **Slack Signature Verification**: All Slack requests verified
- **OAuth State Validation**: Prevents CSRF attacks
- **Input Sanitization**: User input cleaned and validated
- **Rate Limiting**: Built-in FastAPI rate limiting
- **Error Handling**: Graceful error handling and logging

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
1. Check the [Issues](https://github.com/your-repo/issues) page
2. Create a new issue with detailed information
3. Include logs and error messages

## Changelog

### v1.0.0
- Initial release
- Slack OAuth integration
- Wikipedia Q&A with citations
- Multi-turn conversations
- Web interface for installation and logs
- Docker support
- Comprehensive test suite