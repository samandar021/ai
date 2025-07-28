# Claude Computer Use Agent Backend

**Author: Assistant**

## Project Overview

This project is a complete reimplementation of the Anthropic Computer Use Demo as a robust backend API system. It transforms the original Streamlit-based experimental interface into a production-ready FastAPI backend with session management, real-time streaming capabilities, and persistent data storage.

### Key Features

- **FastAPI Backend**: Modern, async Python web framework with automatic API documentation
- **Session Management**: Chat-like session handling with persistent storage
- **Real-time Streaming**: WebSocket connections for live agent progress updates
- **Computer Use Integration**: Full integration with Anthropic's computer use capabilities
- **Database Persistence**: SQLAlchemy-based data layer with Alembic migrations
- **VNC Integration**: Remote desktop viewing capabilities
- **Docker Support**: Complete containerization for development and production

### Architecture

The system follows a clean architecture pattern with clear separation of concerns:

```
User → Frontend → FastAPI → Agent Service → Computer Use Tools → VNC Desktop
                    ↓
                Database (Session & Message Storage)
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- Anthropic API Key

### Environment Setup

1. Copy the environment template:
```bash
cp .env.example .env
```

2. Edit `.env` and set your Anthropic API key:
```
ANTHROPIC_API_KEY=your_api_key_here
```

### Running with Docker (Recommended)

```bash
# Start all services
docker-compose up --build

# The API will be available at http://localhost:8000
# The frontend demo will be available at http://localhost:3000
# VNC viewer will be available at http://localhost:6080
```

### Local Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Documentation

Once the server is running, visit:
- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **ReDoc**: http://localhost:8000/redoc (Alternative API documentation)

### Core Endpoints

#### Session Management
- `POST /api/v1/sessions/` - Create a new chat session
- `GET /api/v1/sessions/` - List all sessions
- `GET /api/v1/sessions/{session_id}` - Get session details
- `DELETE /api/v1/sessions/{session_id}` - Delete a session

#### Message Handling
- `POST /api/v1/sessions/{session_id}/messages/` - Send a message to a session
- `GET /api/v1/sessions/{session_id}/messages/` - Get session message history
- `WebSocket /api/v1/sessions/{session_id}/ws` - Real-time session updates

#### Agent Interaction
- `POST /api/v1/sessions/{session_id}/start` - Start agent processing
- `POST /api/v1/sessions/{session_id}/stop` - Stop agent processing

## Usage Examples

### Creating a New Session

```bash
curl -X POST "http://localhost:8000/api/v1/sessions/" \
     -H "Content-Type: application/json" \
     -d '{"title": "Weather Search Task"}'
```

### Sending a Message

```bash
curl -X POST "http://localhost:8000/api/v1/sessions/{session_id}/messages/" \
     -H "Content-Type: application/json" \
     -d '{"content": "Search the weather in Dubai", "message_type": "user"}'
```

### WebSocket Connection

```javascript
const ws = new WebSocket(`ws://localhost:8000/api/v1/sessions/${sessionId}/ws`);
ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Real-time update:', data);
};
```

## Demo Usage Cases

### Case 1: Dubai Weather Search

1. **Create Session**: Start a new agent task session
2. **Send Message**: "Search the weather in Dubai"
3. **Watch Progress**: The agent will:
   - Open Firefox browser
   - Navigate to Google
   - Search for "weather in Dubai"
   - Extract and summarize results
4. **View Results**: Get real-time updates and final summary

### Case 2: San Francisco Weather Search

1. **Create Session**: Start another new agent task session
2. **Send Message**: "Search the weather in San Francisco"
3. **Watch Progress**: Similar workflow as Case 1
4. **Verify History**: Both sessions are stored and retrievable

## Project Structure

```
computer_use_backend/
├── app/
│   ├── api/v1/endpoints/          # API route handlers
│   ├── core/                      # Configuration and security
│   ├── db/                        # Database layer
│   ├── models/                    # Data models
│   ├── services/                  # Business logic
│   ├── tools/                     # Computer use tools
│   └── utils/                     # Utility functions
├── frontend/                      # Simple frontend demo
├── tests/                         # Test suite
├── scripts/                       # Utility scripts
├── docs/                          # Documentation
└── docker/                        # Docker configurations
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/unit/test_sessions.py
```

### Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Code Quality

```bash
# Format code
black app/ tests/

# Check linting
ruff check app/ tests/

# Type checking
mypy app/
```

## Production Deployment

### Using Docker Compose

```bash
# Production build
docker-compose -f docker-compose.prod.yml up --build -d
```

### Environment Variables

Required environment variables for production:

```
ANTHROPIC_API_KEY=your_api_key
DATABASE_URL=postgresql://user:pass@host:port/dbname
SECRET_KEY=your_secret_key
ENVIRONMENT=production
LOG_LEVEL=INFO
```

## Architecture Deep Dive

### Backend Components

1. **FastAPI Application**: Modern async web framework with automatic API documentation
2. **Session Service**: Manages chat sessions and their lifecycle
3. **Agent Service**: Orchestrates the computer use agent interactions
4. **WebSocket Manager**: Handles real-time communication with clients
5. **Database Layer**: SQLAlchemy models with repository pattern
6. **Tool Integration**: Direct integration with Anthropic's computer use tools

### Real-time Communication

The system uses WebSockets to provide real-time updates during agent execution:

1. Client connects to WebSocket endpoint
2. Agent service emits progress events
3. WebSocket manager broadcasts to connected clients
4. Frontend receives live updates and displays progress

### Database Design

- **Sessions Table**: Stores session metadata (ID, title, created_at, status)
- **Messages Table**: Stores all messages (user queries, agent responses, tool calls)
- **Foreign Key Relations**: Messages belong to sessions

## Troubleshooting

### Common Issues

1. **VNC Connection Failed**: Ensure the VNC service is running in Docker
2. **Database Connection Error**: Check DATABASE_URL in .env file
3. **Anthropic API Errors**: Verify ANTHROPIC_API_KEY is set correctly
4. **WebSocket Disconnection**: Check firewall settings and network connectivity

### Logs

```bash
# View application logs
docker-compose logs -f api

# View database logs
docker-compose logs -f db

# View VNC logs
docker-compose logs -f vnc
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make your changes
4. Add tests for new functionality
5. Run the test suite: `pytest`
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built on top of Anthropic's computer-use-demo
- Inspired by the need for production-ready computer use applications
- Thanks to the FastAPI and SQLAlchemy communities

---

**Note**: This project is for demonstration purposes and should be secured appropriately before production use.