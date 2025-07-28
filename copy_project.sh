#!/bin/bash

# Computer Use Agent Backend - File Copy Script
# This script shows you exactly what files to copy from the workspace

echo "=== Computer Use Agent Backend Project Files ==="
echo ""
echo "Create the following directory structure on your local machine:"
echo ""

# Create directory structure
echo "mkdir -p computer_use_backend/{app/{api/v1/endpoints,core,db/{migrations/versions,repositories},models,services/{agents,sessions,websocket},tools,utils},frontend/static/{css,js},tests/{unit,integration,e2e},scripts,docs/demo,docker/{development,production}}"
echo ""

echo "Then copy these files:"
echo ""

# List all files to copy
cat << 'EOF'
# Root files
README.md
requirements.txt
.env.example
.gitignore
Dockerfile
docker-compose.yml
Makefile
alembic.ini

# App files
app/__init__.py
app/main.py
app/core/__init__.py
app/core/config.py
app/core/logging.py
app/core/security.py
app/db/__init__.py
app/db/database.py
app/db/migrations/__init__.py
app/db/migrations/versions/__init__.py
app/db/repositories/__init__.py
app/models/__init__.py
app/models/database.py
app/models/schemas.py
app/api/__init__.py
app/api/v1/__init__.py
app/api/v1/endpoints/__init__.py
app/api/v1/endpoints/sessions.py
app/api/v1/endpoints/messages.py
app/api/v1/endpoints/websocket.py
app/services/__init__.py
app/services/agents/__init__.py
app/services/agents/agent_service.py
app/services/agents/loop.py
app/services/sessions/__init__.py
app/services/sessions/session_service.py
app/services/websocket/__init__.py
app/services/websocket/manager.py
app/tools/__init__.py
app/tools/base.py
app/tools/bash.py
app/tools/collection.py
app/tools/computer.py
app/tools/edit.py
app/tools/groups.py
app/tools/run.py
app/utils/__init__.py

# Frontend files
frontend/index.html
frontend/static/css/style.css
frontend/static/js/app.js

EOF

echo ""
echo "=== After copying files, run these commands in your local directory ==="
echo ""
echo "cd computer_use_backend"
echo "cp .env.example .env"
echo "# Edit .env file with your ANTHROPIC_API_KEY"
echo "docker-compose up --build"
echo ""
echo "=== Access URLs ==="
echo "API Server: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo "Frontend Demo: http://localhost:3001"
echo "VNC Desktop: http://localhost:3000"
echo ""