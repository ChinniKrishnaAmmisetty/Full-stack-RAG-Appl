"""Vector database operations using Milvus with per-user isolated collections."""

import logging
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Embedding dimension for Gemini gemini-embedding-001
EMBEDDING_DIM = 3072

_connected = False


def _ensure_connection():
    """Ensure connection to Milvus server."""
    global _connected
    if not _connected:
        connections.connect(
            alias="default",
            host=settings.MILVUS_HOST,
            port=settings.MILVUS_PORT,
        )
        _connected = True
        logger.info(f"Connected to Milvus at {settings.MILVUS_HOST}:{settings.MILVUS_PORT}")


def _get_or_create_collection() -> Collection:
    """Get or create the global Milvus collection for all users."""
    _ensure_connection()
    col_name = "rag_documents"

    if utility.has_collection(col_name):
        collection = Collection(col_name)
        collection.load()
        return collection

    # Define schema with user_id for metadata filtering
    fields = [
        FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=200, is_primary=True),
        FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=36),
        FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
        FieldSchema(name="chunk_index", dtype=DataType.INT64),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
    ]
    schema = CollectionSchema(fields=fields, description="Global RAG vectors collection")
    collection = Collection(name=col_name, schema=schema)

    # Create index for fast search
    index_params = {
        "metric_type": "COSINE",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 128},
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    collection.load()

    logger.info(f"Created global Milvus collection '{col_name}'")
    return collection


def add_document_chunks(
    user_id: str,
    document_id: str,
    chunks: list[str],
    embeddings: list[list[float]],
) -> None:
    """Store document chunks and their embeddings in the user's Milvus collection."""
    if not chunks or not embeddings:
        return

    collection = _get_or_create_collection()

    ids = [f"{document_id}_chunk_{i}" for i in range(len(chunks))]
    user_ids = [user_id] * len(chunks)
    doc_ids = [document_id] * len(chunks)
    chunk_indices = list(range(len(chunks)))

    # Truncate texts to fit Milvus VARCHAR limit
    safe_chunks = [text[:65000] for text in chunks]

    data = [ids, user_ids, doc_ids, chunk_indices, safe_chunks, embeddings]
    try:
        collection.insert(data)
        collection.flush()
        logger.info(f"Added {len(chunks)} chunks for document {document_id}")
    except Exception as e:
        logger.error(f"Failed to insert chunks into Milvus: {e}")
        raise


def query_similar_chunks(
    user_id: str,
    query_embedding: list[float],
    top_k: int = 10,
) -> list[dict]:
    """Query the most similar chunks from the global Milvus collection for a specific user."""
    _ensure_connection()
    col_name = "rag_documents"

    if not utility.has_collection(col_name):
        logger.warning(f"Global collection '{col_name}' does not exist.")
        return []

    collection = Collection(col_name)
    collection.load()

    search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}
    
    # Metadata filtering: Only search chunks belonging to this user
    expr = f"user_id == '{user_id}'"

    results = collection.search(
        data=[query_embedding],
        anns_field="embedding",
        param=search_params,
        limit=top_k,
        expr=expr,
        output_fields=["text", "document_id", "id"],
    )

    output = []
    for hits in results:
        for hit in hits:
            output.append({
                "id": hit.entity.get("id"),
                "text": hit.entity.get("text", ""),
                "document_id": hit.entity.get("document_id", ""),
                "distance": hit.distance,
            })

    return output


def _sanitize_milvus_input(value: str) -> str:
    """Sanitize input for use in Milvus expressions to prevent injection attacks."""
    # Remove characters that could break Milvus expressions
    dangerous_chars = ['"', "'", "\\", ";", "(", ")", "==", "||", "&&"]
    sanitized = value
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, "")
    return sanitized.strip()


def query_keyword_chunks(
    user_id: str,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """Perform a keyword search using Milvus LIKE operations."""
    _ensure_connection()
    col_name = "rag_documents"

    if not utility.has_collection(col_name):
        return []

    collection = Collection(col_name)
    collection.load()

    # Extremely basic stopword removal to find important keywords
    stop_words = {"what", "is", "the", "in", "a", "an", "of", "and", "to", "for", "with", "on", "at", "by", "from", "about", "as", "into", "like", "through", "after", "over", "between", "out", "against", "during", "without", "before", "under", "around", "among"}
    words = [w.strip("?,.!;'\"").lower() for w in query.split()]
    keywords = [_sanitize_milvus_input(w) for w in words if w and w not in stop_words and len(w) > 2]
    keywords = [kw for kw in keywords if kw]  # Remove empty strings after sanitization

    if not keywords:
        return []

    # Sanitize user_id for expression safety
    safe_user_id = _sanitize_milvus_input(user_id)

    # Build LIKE expression with sanitized inputs
    like_clauses = [f'text like "%{kw}%"' for kw in keywords]
    joined_likes = " or ".join(like_clauses)
    expr = f"user_id == '{safe_user_id}' and ({joined_likes})"

    try:
        results = collection.query(
            expr=expr,
            output_fields=["text", "document_id", "id"],
            limit=limit
        )
        
        output = []
        for hit in results:
            output.append({
                "id": hit.get("id"),
                "text": hit.get("text", ""),
                "document_id": hit.get("document_id", ""),
                "distance": 0.0, # Keyword matches don't have vector distance
            })
        return output
    except Exception as e:
        logger.error(f"Keyword search failed: {e}")
        return []


def delete_document_chunks(user_id: str, document_id: str) -> None:
    """Delete all chunks for a specific document from the global collection."""
    _ensure_connection()
    col_name = "rag_documents"

    if not utility.has_collection(col_name):
        return

    collection = Collection(col_name)
    collection.load()

    # Delete by expression (matching both user_id and document_id for safety)
    expr = f"user_id == '{user_id}' and document_id == '{document_id}'"
    try:
        collection.delete(expr)
        collection.flush()
        logger.info(f"Deleted chunks for document {document_id}")
    except Exception as e:
        logger.error(f"Failed to delete chunks from Milvus: {e}")
