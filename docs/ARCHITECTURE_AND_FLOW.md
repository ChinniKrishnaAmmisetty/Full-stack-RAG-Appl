# RAG Chatbot Architecture and Flow Diagrams

This document describes the current architecture and execution flow of the project in a report-friendly format.
The diagrams are based on the code currently present in this repository.

Database note:
- The current active configuration uses PostgreSQL + SQLAlchemy + asyncpg through `backend/environment/.env`.
- The code still contains a SQLite fallback in `backend/app/config.py` if `DATABASE_URL` is omitted.

## 1. System Architecture Overview

```mermaid
flowchart LR
    U[End User]
    B[Browser]

    subgraph FE["Frontend Layer (React + Vite)"]
        APP[App.jsx<br/>Route Guarding]
        AUTHCTX[AuthContext.jsx<br/>JWT session state]
        THEME[ThemeContext.jsx<br/>Theme state]
        CHATUI[ChatPage.jsx<br/>Chat workspace]
        DOCUI[Documents.jsx<br/>Upload management]
        DASHUI[Dashboard.jsx<br/>Analytics view]
        APIJS[api.js<br/>Axios + SSE client]
        COMP[Sidebar / InputBox / ChatMessage / AnalyticsPanel]
    end

    subgraph BE["Backend Layer (FastAPI)"]
        MAIN[main.py<br/>App startup, CORS, health routes]
        AUTHR[auth_router.py]
        DOCR[document_router.py]
        CHATR[chat_router.py]
        AUTHS[auth.py<br/>JWT + password hashing]
        DOCSVC[document_service.py<br/>Validation, extraction, chunking]
        EMBSVC[embedding_service.py<br/>Embedding requests]
        VECSVC[vector_service.py<br/>Chunk storage + retrieval]
        RAGSVC[rag_service.py<br/>Hybrid retrieval, reranking, prompting, generation]
        OLLSVC[ollama_service.py<br/>Ollama clients + normalized errors]
        RLSVC[retrieval_policy.py / rl_agent.py / reward_function.py]
    end

    subgraph DATA["Persistent Data Layer"]
        DB[(PostgreSQL + SQLAlchemy + asyncpg)]
        USERS[(users)]
        DOCS[(documents)]
        CHUNKS[(document_chunks)]
        SESS[(chat_sessions)]
        MSGS[(chat_messages)]
    end

    subgraph MODEL["Local Model Layer"]
        OLLAMA[Ollama Server]
        EMBMODEL[nomic-embed-text]
        GENMODEL[qwen2.5:1.5b]
        RERANKER[cross-encoder/ms-marco-MiniLM-L-6-v2]
    end

    U --> B --> APP
    APP --> AUTHCTX
    APP --> THEME
    APP --> CHATUI
    APP --> DOCUI
    APP --> DASHUI
    CHATUI --> COMP
    DOCUI --> COMP
    CHATUI --> APIJS
    DOCUI --> APIJS
    DASHUI --> APIJS

    APIJS --> MAIN
    MAIN --> AUTHR
    MAIN --> DOCR
    MAIN --> CHATR

    AUTHR --> AUTHS
    AUTHS --> DB

    DOCR --> DOCSVC
    DOCR --> EMBSVC
    DOCR --> VECSVC

    CHATR --> RAGSVC
    CHATR --> AUTHS
    CHATR --> DB

    RAGSVC --> EMBSVC
    RAGSVC --> VECSVC
    RAGSVC --> OLLSVC
    CHATR --> RLSVC
    RLSVC --> EMBSVC
    RLSVC --> VECSVC
    RLSVC --> RERANKER

    DB --> USERS
    DB --> DOCS
    DB --> CHUNKS
    DB --> SESS
    DB --> MSGS

    EMBSVC --> OLLAMA
    RAGSVC --> OLLAMA
    OLLSVC --> OLLAMA
    OLLAMA --> EMBMODEL
    OLLAMA --> GENMODEL
    RAGSVC --> RERANKER
    VECSVC --> CHUNKS
```

## 2. Logical Component View

| Layer | Main Files | Responsibility |
|---|---|---|
| UI | `frontend/src/App.jsx`, `pages/*.jsx`, `components/*.jsx` | Routing, chat UI, document UI, dashboard, status panel |
| Frontend Integration | `frontend/src/api.js` | Axios REST calls, SSE stream parsing, token handling |
| API Entry | `backend/app/main.py` | FastAPI app setup, middleware, CORS, health checks |
| Auth | `backend/app/auth.py`, `backend/app/routers/auth_router.py` | Register, login, JWT issue/validation, password reset |
| Document Pipeline | `backend/app/routers/document_router.py`, `document_service.py`, `embedding_service.py`, `vector_service.py` | Upload, validate, extract text, chunk, embed, store chunks |
| Chat / RAG | `backend/app/routers/chat_router.py`, `rag_service.py` | Session handling, streaming, retrieval, reranking, prompt building, grounded generation |
| Retrieval Store | `backend/app/models.py`, `vector_service.py` | Chunk persistence and search over stored embeddings + keywords |
| Model Access | `backend/app/services/ollama_service.py` | Shared Ollama clients and error normalization |
| Evaluation / RL | `backend/retrieval_policy.py`, `backend/rl_agent.py`, `backend/reward_function.py`, `backend/evaluation_runner.py` | Experimental retrieval policy selection and offline evaluation |

## 3. Database / Entity Relationship Diagram

```mermaid
erDiagram
    USER {
        string id PK
        string email
        string username
        string hashed_password
        datetime created_at
    }

    DOCUMENT {
        string id PK
        string user_id FK
        string filename
        string file_type
        int file_size
        int chunk_count
        string status
        string error_message
        datetime created_at
    }

    DOCUMENT_CHUNK {
        string id PK
        string user_id
        string document_id FK
        int chunk_index
        text text
        json embedding
        datetime created_at
    }

    CHAT_SESSION {
        string id PK
        string user_id FK
        string title
        datetime created_at
    }

    CHAT_MESSAGE {
        string id PK
        string session_id FK
        string role
        text content
        datetime created_at
    }

    USER ||--o{ DOCUMENT : uploads
    USER ||--o{ CHAT_SESSION : owns
    DOCUMENT ||--o{ DOCUMENT_CHUNK : contains
    CHAT_SESSION ||--o{ CHAT_MESSAGE : stores
```

## 4. Authentication Flow

```mermaid
flowchart TD
    A[User opens login or register page]
    B[Frontend submits credentials]
    C[FastAPI auth_router]
    D{Register or Login}
    E[Validate uniqueness or verify password]
    F[Generate JWT access token]
    G[Return token to frontend]
    H[AuthContext stores token in localStorage]
    I[Protected routes enabled]
    J[Later API request]
    K[api.js attaches Authorization Bearer token]
    L[get_current_user dependency validates JWT]
    M[User record loaded from PostgreSQL via SQLAlchemy]
    N[Authorized endpoint continues]

    A --> B --> C --> D
    D --> E --> F --> G --> H --> I
    I --> J --> K --> L --> M --> N
```

## 5. Document Upload and Indexing Flow

```mermaid
flowchart TD
    A[User uploads file in Documents page]
    B[POST /api/documents/upload]
    C[Validate extension and file size]
    D[Save file temporarily in upload directory]
    E[Create Document row with status = processing]
    F[Background task _process_document starts]
    G[Validate file content against type]
    H[Extract raw text from PDF / DOCX / TXT / CSV / XLSX / MD]
    I{Text extracted?}
    J[Split text into overlapping chunks]
    K{Chunks created?}
    L[Generate embeddings for all chunks via Ollama]
    M[Persist document chunks + embeddings]
    N[Update Document status = ready and chunk_count]
    O[Remove temporary upload file]
    P[Document visible as ready in UI]
    Q[Mark Document status = failed with error_message]

    A --> B --> C --> D --> E --> F --> G --> H --> I
    I -- No --> Q --> O
    I -- Yes --> J --> K
    K -- No --> Q --> O
    K -- Yes --> L --> M --> N --> O --> P
```

## 6. Main Chat / RAG Processing Flow

```mermaid
flowchart TD
    A[User sends question from ChatPage]
    B{Active session exists?}
    C[Create new session if needed]
    D[POST /api/chat/sessions/{id}/messages/stream]
    E[Save user message in chat_messages]
    F[Load recent chat history]
    G[Emit SSE status: Preparing request]
    H[Detect response mode]
    I[Emit SSE status: Building query embedding]
    J[generate_query_embedding_async]
    K[Emit SSE status: Running hybrid search]
    L[query_similar_chunks]
    M[query_keyword_chunks]
    N[merge_and_rerank]
    O[apply_cross_encoder_reranking]
    P[build_sources_with_db]
    Q[Emit SSE status: Extracting matching chunks]
    R{Relevant chunks found?}
    S[Return fallback answer]
    T[build_rag_prompt + SYSTEM_PROMPT]
    U[Emit SSE status: Generating grounded answer]
    V[Stream LLM response from Ollama]
    W[Accumulate assistant answer]
    X[Save assistant message in chat_messages]
    Y[Emit SSE done event]
    Z[Frontend replaces temporary message with saved response]

    A --> B
    B -- No --> C --> D
    B -- Yes --> D
    D --> E --> F --> G --> H --> I --> J --> K --> L --> M --> N --> O --> P --> Q --> R
    R -- No --> S --> X --> Y --> Z
    R -- Yes --> T --> U --> V --> W --> X --> Y --> Z
```

## 7. Streaming Status and Answer Sequence

```mermaid
sequenceDiagram
    actor User
    participant UI as ChatPage / ChatMessage
    participant API as frontend/api.js
    participant Router as chat_router.py
    participant RAG as rag_service.py
    participant Vec as vector_service.py
    participant DB as PostgreSQL + SQLAlchemy + asyncpg
    participant Ollama as Ollama

    User->>UI: Enter question and click Send
    UI->>API: streamMessage(sessionId, content)
    API->>Router: POST /messages/stream
    Router->>DB: Save user message
    Router->>RAG: generate_rag_response_stream(...)

    RAG-->>Router: status Preparing request
    Router-->>API: SSE status
    API-->>UI: Update live status list

    RAG-->>Router: status Building query embedding
    RAG->>Ollama: Generate query embedding
    Router-->>API: SSE status
    API-->>UI: Update live status list

    RAG-->>Router: status Running hybrid search
    RAG->>Vec: Dense vector search
    RAG->>Vec: Keyword search
    Router-->>API: SSE status
    API-->>UI: Update live status list

    RAG->>RAG: Hybrid merge + rerank
    RAG-->>Router: status Extracting matching chunks
    Router-->>API: SSE status
    API-->>UI: Update live status list

    RAG-->>Router: sources payload
    Router-->>API: SSE sources
    API-->>UI: Render matched sources

    RAG-->>Router: status Generating grounded answer
    RAG->>Ollama: Stream final answer
    loop token stream
        Ollama-->>RAG: text chunk
        RAG-->>Router: chunk
        Router-->>API: SSE chunk
        API-->>UI: Append streamed text
    end

    Router->>DB: Save assistant message
    Router-->>API: SSE done
    API-->>UI: Replace temp message with saved message
```

## 8. Internal Retrieval Logic

```mermaid
flowchart LR
    Q[User query]
    QE[Query embedding]
    VS[Vector similarity search]
    KS[Keyword search]
    HM[Weighted hybrid merge]
    RR[Cross-encoder reranking]
    FC[Final chunks]
    PR[Prompt construction]
    GA[Grounded answer generation]

    Q --> QE
    Q --> KS
    QE --> VS
    VS --> HM
    KS --> HM
    HM --> RR --> FC --> PR --> GA
```

## 9. RL Retrieval Evaluation Flow

This path is separate from the normal chat endpoint and is used for experimentation and evaluation.

```mermaid
flowchart TD
    A[Client calls /api/chat/rl/query]
    B[Load QLearningAgent]
    C[build_state from query length and probe retrieval scores]
    D[Select action from Q-table]
    E[Map action to top_k and reranker usage]
    F[retrieve_chunks]
    G{use_reranker?}
    H[Optional cross-encoder reranking]
    I[build_sources_with_db]
    J[build_rag_prompt]
    K[Generate answer with Ollama]
    L[compute_reward]
    M{evaluation mode?}
    N[Update Q-table and decay epsilon]
    O[Return RLQueryResponse]

    A --> B --> C --> D --> E --> F --> G
    G -- Yes --> H --> I
    G -- No --> I
    I --> J --> K --> L --> M
    M -- No --> N --> O
    M -- Yes --> O
```

## 10. End-to-End Summary

The runtime architecture can be understood as four connected pipelines:

1. Authentication pipeline: React auth pages -> FastAPI auth router -> JWT -> protected route access.
2. Document pipeline: Upload -> background extraction -> chunking -> embeddings -> local chunk store.
3. Chat pipeline: Question -> hybrid retrieval -> reranking -> grounded generation -> SSE streaming back to UI.
4. Evaluation pipeline: RL action selection -> retrieval experiment -> reward computation -> Q-table update.

For B.Tech documentation, the most useful diagrams are usually:

- System Architecture Overview
- Document Upload and Indexing Flow
- Main Chat / RAG Processing Flow
- Streaming Status and Answer Sequence
- Database / Entity Relationship Diagram
