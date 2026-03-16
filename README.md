# Multi-RAG Chatbot System

A production-grade Retrieval Augmented Generation (RAG) chatbot that lets users upload documents and ask questions powered by AI.

![Python](https://img.shields.io/badge/Python-3.11+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green) ![React](https://img.shields.io/badge/React-18-blue) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)

## Architecture

```
Frontend (React + Vite)  →  Backend (FastAPI)  →  PostgreSQL (users, docs, chat)
                                               →  ChromaDB (vector embeddings)
                                               →  nomic-embed-text (embeddings)
                                               →  Gemini API (LLM responses)
```

## Features

- **Authentication**: JWT-based login/register with bcrypt password hashing
- **Document Upload**: PDF, DOCX, TXT — text extraction, chunking, embedding
- **Isolated Knowledge Bases**: Each user has their own vector namespace
- **RAG Pipeline**: nomic-embed-text embeddings + ChromaDB vector search + Gemini API
- **Chat Interface**: ChatGPT-like UI with chat history and markdown rendering
- **Document Management**: Upload, view status, and delete documents
- **Scalability**: Async APIs, connection pooling, background processing, rate limiting

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** and npm
- **PostgreSQL 14+** (running and accessible)
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

> **Note**: The first startup will download the `nomic-embed-text` model (~275 MB). The database tables are auto-created on startup.

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
│   │       ├── embedding_service.py  # nomic-embed-text
│   │       ├── vector_service.py     # ChromaDB operations
│   │       └── rag_service.py        # RAG pipeline + Gemini
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js
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
│   │   │   └── DocumentList.jsx
│   │   └── index.css
│   ├── package.json
│   └── vite.config.js
└── README.md
```

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
- [ ] Configure `DATABASE_URL` with production credentials
- [ ] Set `GEMINI_API_KEY`
- [ ] Use HTTPS in production
- [ ] Set up a reverse proxy (nginx) for frontend + API
- [ ] Configure proper CORS origins in `main.py`

## System Prompt

The chatbot follows a strict document-only answering rule:

> *"You are a document assistant. Answer questions strictly based on the provided document context. Do not use external knowledge. If the answer cannot be found, respond: 'I could not find the answer in the uploaded documents.'"*

## License

MIT
