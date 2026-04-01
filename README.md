
# Multi-RAG Chatbot System

A production-grade Retrieval Augmented Generation (RAG) chatbot that lets users upload documents and ask questions powered by AI.

![Python](https://img.shields.io/badge/Python-3.11+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green) ![React](https://img.shields.io/badge/React-18-blue) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue) ![Milvus](https://img.shields.io/badge/Milvus-2.4-purple) ![Gemini](https://img.shields.io/badge/Gemini-API-orange)

## Architecture

```
Frontend (React + Vite)  →  Backend (FastAPI)  →  PostgreSQL (users, docs, chat)
                                               →  Milvus (vector database)
                                               →  gemini-embedding-001 (embeddings)
                                               →  Gemini API (LLM responses)
```

## Features

- **Authentication**: JWT-based login/register with bcrypt password hashing
- **Document Upload**: PDF, DOCX, TXT — text extraction, chunking, embedding
- **Isolated Knowledge Bases**: Each user has their own vector namespace
- **RAG Pipeline**: gemini-embedding-001 embeddings + Milvus vector search + Gemini API
- **Hybrid Search**: Vector similarity search + keyword-based search with re-ranking
- **Streaming Responses**: Real-time streamed AI answers with markdown rendering
- **Google OAuth**: Optional Google sign-in alongside email/password auth
- **Chat Interface**: ChatGPT-like UI with chat history and markdown rendering
- **Document Management**: Upload, view status, and delete documents
- **Scalability**: Async APIs, connection pooling, background processing, rate limiting

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** and npm
- **PostgreSQL 14+** (running and accessible)
- **Docker & Docker Compose** (for Milvus vector database)
- **Gemini API Key** (from [Google AI Studio](https://aistudio.google.com/))

## Quick Start

### 1. Clone & Configure

```bash
cd backend
copy .env.example .env
# Edit .env with your values:
#   DATABASE_URL=postgresql+asyncpg://postgres:yourpassword@localhost:5432/rag_chatbot
#   SECRET_KEY=a-random-secret-key
#   GEMINI_API_KEY=your-gemini-api-key
```

### 2. Create the PostgreSQL Database

```sql
CREATE DATABASE rag_chatbot;
```

### 3. Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # On Windows
# source venv/bin/activate   # On macOS/Linux

pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> **Note**: Make sure Milvus is running before starting the backend (see Docker Compose section below). The database tables are auto-created on startup.

### 4. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### 5. Open the App

Navigate to **http://localhost:5173** in your browser.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/register` | Register a new user |
| `POST` | `/api/auth/login` | Login and get JWT token |
| `GET` | `/api/auth/me` | Get current user info |
| `POST` | `/api/documents/upload` | Upload a document (multipart) |
| `GET` | `/api/documents/` | List user's documents |
| `DELETE` | `/api/documents/{id}` | Delete a document |
| `POST` | `/api/chat/sessions` | Create a chat session |
| `GET` | `/api/chat/sessions` | List chat sessions |
| `GET` | `/api/chat/sessions/{id}/messages` | Get session messages |
| `POST` | `/api/chat/sessions/{id}/messages` | Send message (RAG) |
| `DELETE` | `/api/chat/sessions/{id}` | Delete a chat session |
| `GET` | `/api/health` | Health check |

## Folder Structure

```
RAG_chatbot/
├── docker-compose.yml           # Milvus, PostgreSQL, Backend, Frontend
├── .env.example                 # Environment variable template
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry
│   │   ├── config.py            # Settings from .env
│   │   ├── database.py          # Async SQLAlchemy
│   │   ├── models.py            # ORM models
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── auth.py              # JWT + bcrypt
│   │   ├── routers/
│   │   │   ├── auth_router.py
│   │   │   ├── document_router.py
│   │   │   └── chat_router.py
│   │   └── services/
│   │       ├── document_service.py   # Text extraction + chunking
│   │       ├── embedding_service.py  # gemini-embedding-001
│   │       ├── vector_service.py     # Milvus operations
│   │       └── rag_service.py        # RAG pipeline + Gemini
│   ├── environment/.env
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js
│   │   ├── main.jsx
│   │   ├── context/AuthContext.jsx
│   │   ├── pages/
│   │   │   ├── LoginPage.jsx
│   │   │   ├── RegisterPage.jsx
│   │   │   └── ChatPage.jsx
│   │   ├── components/
│   │   │   ├── Sidebar.jsx
│   │   │   ├── ChatMessage.jsx
│   │   │   ├── ChatInput.jsx
│   │   │   ├── FileUpload.jsx
│   │   │   ├── DocumentList.jsx
│   │   │   ├── SettingsModal.jsx
│   │   │   ├── AiBot.jsx
│   │   │   └── MatrixBackground.jsx
│   │   ├── utils/
│   │   └── index.css
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## Docker Compose Deployment

The project includes a full `docker-compose.yml` that spins up all services:

```bash
# Start all services (Milvus + dependencies, PostgreSQL, Backend, Frontend)
docker compose up -d

# Check service health
docker compose ps

# View logs
docker compose logs -f backend
```

**Services included:**

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `milvus` | milvusdb/milvus:v2.4.13 | 19530 | Vector database |
| `postgres` | postgres:16-alpine | — | Relational database |
| `etcd` | coreos/etcd:v3.5.16 | — | Milvus metadata store |
| `minio` | minio/minio | — | Milvus object storage |
| `backend` | Custom (FastAPI) | 8000 | API server |
| `frontend` | Custom (React) | 5173 | Web UI |

## Production Deployment

### Scale the Backend

```bash
# Run with multiple workers
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Or use gunicorn with uvicorn workers
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Build the Frontend

```bash
cd frontend
npm run build
# Serve the dist/ folder with nginx or any static file server
```

### Environment Checklist

- [ ] Set a strong `SECRET_KEY` (use `openssl rand -hex 32`)
- [ ] Configure database credentials (`DB_HOST`, `DB_USER`, `DB_PASSWORD`)
- [ ] Set `GEMINI_API_KEY`
- [ ] Configure `MILVUS_HOST` and `MILVUS_PORT`
- [ ] Set `GOOGLE_CLIENT_ID` (if using Google OAuth)
- [ ] Use HTTPS in production
- [ ] Set up a reverse proxy (nginx) for frontend + API
- [ ] Configure proper CORS origins in `main.py`

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 18, Vite |
| **Backend** | FastAPI (Python 3.11+) |
| **Database** | PostgreSQL 16 |
| **Vector DB** | Milvus 2.4 |
| **Embeddings** | gemini-embedding-001 (3072-dim) |
| **LLM** | Gemini API |
| **Auth** | JWT + bcrypt, Google OAuth |
| **Infra** | Docker Compose |

## System Prompt

The chatbot follows a strict document-only answering rule:

> *"You are a document assistant. Answer questions strictly based on the provided document context. Do not use external knowledge. If the answer cannot be found, respond: 'I could not find the answer in the uploaded documents.'"*

## License

MIT
