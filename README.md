# Full Stack RAG Chatbot

A full-stack Retrieval-Augmented Generation (RAG) application for uploading documents, indexing them locally, and asking grounded questions through a React + FastAPI workspace.

![Python](https://img.shields.io/badge/Python-3.11+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green) ![React](https://img.shields.io/badge/React-18-blue) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-configured-blue) ![Ollama](https://img.shields.io/badge/Ollama-local-green)

## Current Implementation

This repository currently runs with:

- React + Vite on the frontend
- FastAPI on the backend
- SQLAlchemy models for users, documents, chat sessions, messages, and document chunks
- PostgreSQL + SQLAlchemy + asyncpg in the current `backend/environment/.env` configuration
- SQLite remains available only as a fallback when `DATABASE_URL` is not provided
- Ollama for embeddings (`nomic-embed-text`) and generation (`qwen2.5:1.5b`)
- Hybrid retrieval using vector similarity + keyword search
- Cross-encoder reranking
- An experimental reinforcement learning evaluation path for retrieval policy selection

Important: the working app stores chunk embeddings in the application database. It does not require a separate vector database for the current local setup.

## Architecture

```text
Frontend (React + Vite)
  -> Backend API (FastAPI)
  -> PostgreSQL + SQLAlchemy + asyncpg storage for users, documents, sessions, messages, and chunk embeddings
  -> Local retrieval layer:
       - dense similarity search over stored chunk embeddings
       - keyword search
       - weighted hybrid merge
       - cross-encoder reranking
  -> Ollama:
       - nomic-embed-text for embeddings
       - qwen2.5:1.5b for answer generation
```

Detailed documentation diagrams:

- `docs/ARCHITECTURE_AND_FLOW.md` - detailed architecture, database, upload flow, RAG flow, SSE sequence, and RL flow diagrams

## Features

- JWT authentication with register, login, current-user, and development-mode password reset flow
- Document upload and processing for `pdf`, `docx`, `txt`, `csv`, `xlsx`, and `md`
- Background extraction, recursive chunking, embedding generation, and indexing
- Session-based chat history
- Streaming assistant responses with source attribution
- Dashboard and document management pages
- Local health checks for both the backend and Ollama
- Evaluation scripts for baseline, reranker, and RL-based retrieval experiments

## Quick Start

### 1. Install and prepare Ollama

Install Ollama and make sure it is running locally. Pull the required models:

```bash
ollama pull qwen2.5:1.5b
ollama pull nomic-embed-text
```

If Ollama is not already running as a background service, start it with:

```bash
ollama serve
```

### 2. Start the backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

In the current repository configuration, the backend uses PostgreSQL + SQLAlchemy + asyncpg through `backend/environment/.env`.

### 3. Backend environment configuration

The backend loads settings from:

```text
backend/environment/.env
```

If that file does not exist, the app falls back to the defaults defined in `backend/app/config.py`, including local SQLite.

The current checked-in environment template and active local configuration point to PostgreSQL + SQLAlchemy + asyncpg.

If you want to create or change an `.env` file, note that:

- `backend/environment/.env` in this workspace is configured for PostgreSQL
- `backend/environment/.env.example` also contains a PostgreSQL `DATABASE_URL`
- if `DATABASE_URL` is removed entirely, the code falls back to SQLite from `backend/app/config.py`
- if you want SQLite instead, set a SQLite URL explicitly

Example SQLite value:

```text
DATABASE_URL=sqlite+aiosqlite:///./data/rag_chatbot.db
```

Example PostgreSQL format:

```text
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:5432/<database_name>
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open the frontend at the local Vite URL printed in the terminal, usually:

```text
http://127.0.0.1:5173
```

## Frontend Environment

The frontend development proxy template is stored in:

```text
.env.example
```

The main variable is:

```text
VITE_API_PROXY_TARGET=http://127.0.0.1:8000
```

## Key Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/health` | Backend database and chunk-store health |
| `GET` | `/api/health/ollama` | Ollama generation and embedding diagnostics |
| `POST` | `/api/auth/register` | Create a user |
| `POST` | `/api/auth/login` | Sign in with username or email |
| `GET` | `/api/auth/me` | Load current user |
| `POST` | `/api/auth/forgot-password` | Generate a development reset token |
| `POST` | `/api/auth/reset-password` | Reset password using token |
| `POST` | `/api/documents/upload` | Upload and index a document |
| `GET` | `/api/documents/` | List current user documents |
| `DELETE` | `/api/documents/{document_id}` | Delete a document and its chunks |
| `POST` | `/api/chat/sessions` | Create a chat session |
| `GET` | `/api/chat/sessions` | List chat sessions |
| `GET` | `/api/chat/sessions/{id}/messages` | Get messages for a session |
| `POST` | `/api/chat/sessions/{id}/messages` | Non-streaming RAG response |
| `POST` | `/api/chat/sessions/{id}/messages/stream` | Streaming RAG response via SSE |
| `DELETE` | `/api/chat/sessions/{id}` | Delete a chat session |
| `POST` | `/api/chat/rl/query` | Run the experimental RL retrieval path |

## Project Structure

### Backend

- `backend/app/main.py` - FastAPI app startup, middleware, and health routes
- `backend/app/config.py` - environment-backed settings
- `backend/app/database.py` - async database engine and session setup
- `backend/app/models.py` - ORM models for users, documents, chunks, sessions, and messages
- `backend/app/auth.py` - JWT and password hashing utilities
- `backend/app/routers/auth_router.py` - auth endpoints
- `backend/app/routers/document_router.py` - upload, list, and delete document endpoints
- `backend/app/routers/chat_router.py` - chat, streaming, session, and RL endpoints
- `backend/app/services/document_service.py` - extraction, validation, and chunking
- `backend/app/services/embedding_service.py` - Ollama embedding calls
- `backend/app/services/vector_service.py` - local vector search and keyword search
- `backend/app/services/rag_service.py` - prompt building, retrieval merge, reranking, and generation
- `backend/app/services/ollama_service.py` - Ollama client helpers and normalized errors
- `backend/app/evaluation/` - retrieval evaluation helpers
- `backend/evaluation_runner.py` - baseline/reranker/RL evaluation runner
- `backend/retrieval_policy.py` - RL state and action logic
- `backend/reward_function.py` - RL reward calculation
- `backend/rl_agent.py` - tabular Q-learning agent

### Frontend

- `frontend/src/App.jsx` - route setup
- `frontend/src/api.js` - API client and streaming helpers
- `frontend/src/context/AuthContext.jsx` - auth state management
- `frontend/src/context/ThemeContext.jsx` - theme state management
- `frontend/src/pages/ChatPage.jsx` - main chat workspace
- `frontend/src/pages/Documents.jsx` - upload and document management UI
- `frontend/src/pages/Dashboard.jsx` - workspace overview page
- `frontend/src/components/Sidebar.jsx` - navigation and chat session list
- `frontend/src/components/ChatMessage.jsx` - answer and source rendering
- `frontend/src/components/InputBox.jsx` - chat input and voice capture
- `frontend/src/components/AnalyticsPanel.jsx` - chat analytics side panel

## Evaluation and RL

The repository includes scripts and saved outputs for retrieval and policy evaluation:

- `backend/evaluate.py` - retrieval evaluation CLI
- `backend/evaluation_runner.py` - baseline, reranker, RL training, RL evaluation, and summary generation
- `backend/plots.py` - builds comparison plots from saved results
- `backend/results/` - saved JSON, CSV, and graph artifacts
- `backend/qtable.json` - saved Q-table for the RL policy

These evaluation tools are separate from the normal chat flow. The standard chat experience uses the main hybrid retrieval + reranking pipeline.

## Notes

- Document vectors are stored locally in the application database for a simple, Docker-free setup.
- The current implementation is optimized for local development and project demonstration rather than large-scale production retrieval.
- Password reset is a development workflow in this repository; the reset token is returned by the API instead of being emailed.

## Environment Files

- `backend/environment/.env` - active backend environment file loaded by the app
- `backend/environment/.env.example` - backend template with example values
- `.env.example` - frontend Vite proxy template

Do not commit real `.env` files or secrets.

## License

MIT
