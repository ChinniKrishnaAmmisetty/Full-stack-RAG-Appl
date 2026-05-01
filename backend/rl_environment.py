# Requirements: ollama
from __future__ import annotations

import logging
import time
from typing import Any

from app.config import get_settings
from app.services.ollama_service import get_async_client
from app.services.rag_service import SYSTEM_PROMPT, build_rag_prompt, build_sources_with_db

from retrieval_policy import retrieve_chunks
from reward_function import compute_reward

settings = get_settings()
logger = logging.getLogger(__name__)


class RLEnvironment:
    def __init__(self, user_id: str) -> None:
        self.user_id = user_id

    @staticmethod
    def _doc_ids(chunks: list[dict[str, Any]]) -> list[str]:
        seen: set[str] = set()
        doc_ids: list[str] = []
        for chunk in chunks:
            doc_id = str(
                chunk.get("doc_id")
                or chunk.get("document_id")
                or ""
            ).strip()
            if doc_id and doc_id not in seen:
                seen.add(doc_id)
                doc_ids.append(doc_id)
        return doc_ids

    @staticmethod
    def _rank_metrics(expected_doc_ids: list[str], retrieved_doc_ids: list[str], top_k: int) -> dict[str, float]:
        expected = set(expected_doc_ids)
        ranked = retrieved_doc_ids[:top_k]
        hits = [doc_id for doc_id in ranked if doc_id in expected]
        first_rank = next((index + 1 for index, doc_id in enumerate(ranked) if doc_id in expected), 0)
        recall = len(set(hits)) / max(len(expected), 1)
        return {
            "recall_at_k": recall,
            "precision_at_k": len(hits) / max(top_k, 1),
            "mrr": 0.0 if first_rank == 0 else 1.0 / first_rank,
            "hit_rate": 1.0 if recall > 0 else 0.0,
        }

    async def run_query(self, record: dict[str, Any], top_k: int, use_reranker: bool) -> dict[str, Any]:
        started_at = time.perf_counter()
        logger.info(
            "RL environment run started | user_id=%s | record_id=%s | top_k=%s | reranker=%s",
            self.user_id,
            record["id"],
            top_k,
            use_reranker,
        )
        chunks = await retrieve_chunks(self.user_id, record["query"], top_k, use_reranker)
        final_chunks, sources = await build_sources_with_db(chunks[:top_k])
        if final_chunks:
            prompt = build_rag_prompt(record["query"], final_chunks, chat_history=None, mode="summary")
            response = await get_async_client().chat(
                model=settings.OLLAMA_LLM_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            answer = response["message"]["content"].strip()
        else:
            answer = "Sorry, please ask only questions related to your uploaded documents only."
        latency = time.perf_counter() - started_at
        reward_parts = await compute_reward(
            expected_doc_ids=record["expected_doc_ids"],
            retrieved_chunks=final_chunks,
            generated_answer=answer,
            expected_answer=record["expected_answer"],
            response_time_seconds=latency,
        )
        retrieved_doc_ids = self._doc_ids(final_chunks)
        logger.info(
            "RL environment run completed | user_id=%s | record_id=%s | retrieved_docs=%s | reward=%.4f | latency=%.3fs",
            self.user_id,
            record["id"],
            len(retrieved_doc_ids),
            reward_parts["reward"],
            latency,
        )
        return {
            "id": record["id"],
            "query": record["query"],
            "top_k": top_k,
            "reranker": use_reranker,
            "retrieved_doc_ids": retrieved_doc_ids,
            "sources": sources,
            "answer": answer,
            "response_latency_seconds": latency,
            **self._rank_metrics(record["expected_doc_ids"], retrieved_doc_ids, top_k),
            **reward_parts,
        }
