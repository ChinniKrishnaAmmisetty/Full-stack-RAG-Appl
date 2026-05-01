"""Pydantic schemas for request and response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=6, max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size: int
    chunk_count: int
    status: str
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionCreate(BaseModel):
    title: Optional[str] = "New Chat"


class ChatSessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    mode: Optional[str] = None


class RLQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=5000)
    expected_doc_ids: list[str] = Field(min_length=1)
    expected_answer: str = Field(min_length=1)
    evaluation: bool = False


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse


class RLQueryResponse(BaseModel):
    state: tuple[int, int, int]
    action_id: int
    top_k: int
    reranker: bool
    answer: str
    reward: float
    retrieval_hit: float
    answer_quality: float
    semantic_similarity: float
    latency_penalty: float
    response_latency_seconds: float
    retrieved_doc_ids: list[str]
    sources: list[dict]
