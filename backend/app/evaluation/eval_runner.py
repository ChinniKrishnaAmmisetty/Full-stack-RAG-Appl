"""
RAG Retrieval Evaluation Runner
================================
Computes Recall@K, Precision@K, and generates performance graphs.

This module ONLY evaluates retrieval quality - it does NOT modify
any existing embedding, retrieval, or generation logic.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

EVAL_OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "eval_output"


def search_vectors(user_id: str, query: str, top_k: int = 5) -> list[str]:
    """Hook into the existing retrieval pipeline and return ranked document IDs."""
    from app.services.embedding_service import generate_query_embedding
    from app.services.vector_service import search_vector_ids

    query_embedding = generate_query_embedding(query)
    return asyncio.run(
        search_vector_ids(
            user_id=user_id,
            query_embedding=query_embedding,
            top_k=top_k,
        )
    )


def compute_recall_at_k(expected_doc_id: str, retrieved_doc_ids: list[str]) -> int:
    """Recall@K: 1 if expected doc is in the retrieved list, else 0."""
    return 1 if expected_doc_id in retrieved_doc_ids else 0


def compute_precision_at_k(expected_doc_id: str, retrieved_doc_ids: list[str], k: int) -> float:
    """Precision@K: 1/K if expected doc is in the retrieved list, else 0."""
    return (1.0 / k) if expected_doc_id in retrieved_doc_ids else 0.0


def evaluate_retrieval(
    user_id: str,
    test_data: list[dict],
    K: int = 5,
) -> dict:
    """Run retrieval evaluation over the test dataset for a given K."""
    recall_scores = []
    precision_scores = []
    query_logs = []

    for i, item in enumerate(test_data, 1):
        query = item["query"]
        expected = item["expected_doc_id"]
        retrieved_docs = search_vectors(user_id=user_id, query=query, top_k=K)

        recall = compute_recall_at_k(expected, retrieved_docs)
        precision = compute_precision_at_k(expected, retrieved_docs, K)

        recall_scores.append(recall)
        precision_scores.append(precision)

        log_entry = {
            "index": i,
            "query": query,
            "expected": expected,
            "retrieved": retrieved_docs,
            "recall": recall,
            "precision": round(precision, 4),
            "hit": expected in retrieved_docs,
        }
        query_logs.append(log_entry)

        status = "HIT" if log_entry["hit"] else "MISS"
        logger.info(
            "[%s/%s] %s | K=%s | Query: \"%s\" | Expected: %s",
            i,
            len(test_data),
            status,
            K,
            query[:60],
            expected,
        )

    final_recall = sum(recall_scores) / len(recall_scores) if recall_scores else 0.0
    final_precision = sum(precision_scores) / len(precision_scores) if precision_scores else 0.0

    return {
        "K": K,
        "num_queries": len(test_data),
        "final_recall": round(final_recall, 4),
        "final_precision": round(final_precision, 4),
        "query_logs": query_logs,
    }


def evaluate_across_k_values(
    user_id: str,
    test_data: list[dict],
    k_values: list[int] | None = None,
) -> list[dict]:
    """Run evaluation at multiple K values for graphing."""
    if k_values is None:
        k_values = [1, 3, 5, 10]

    all_results = []
    for k in k_values:
        logger.info("\n%s", "=" * 60)
        logger.info("  Evaluating Recall@%s / Precision@%s", k, k)
        logger.info("%s", "=" * 60)
        result = evaluate_retrieval(user_id=user_id, test_data=test_data, K=k)
        all_results.append(result)
        logger.info(
            "  -> Recall@%s = %.4f | Precision@%s = %.4f",
            k,
            result["final_recall"],
            k,
            result["final_precision"],
        )

    return all_results


def generate_recall_precision_graph(eval_results: list[dict], save_path: str | None = None) -> str:
    """Generate and save a Recall@K and Precision@K line chart."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.error("matplotlib is required for graph generation. Install with: pip install matplotlib")
        raise

    k_values = [r["K"] for r in eval_results]
    recall_values = [r["final_recall"] for r in eval_results]
    precision_values = [r["final_precision"] for r in eval_results]

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(k_values, recall_values, marker="o", linewidth=2.5, markersize=8, color="#e94560", label="Recall@K")
    ax.plot(k_values, precision_values, marker="s", linewidth=2.5, markersize=8, color="#0f3460", label="Precision@K")

    for k, recall, precision in zip(k_values, recall_values, precision_values):
        ax.annotate(f"{recall:.2f}", (k, recall), textcoords="offset points", xytext=(0, 12), ha="center", fontsize=9, color="#e94560", fontweight="bold")
        ax.annotate(f"{precision:.2f}", (k, precision), textcoords="offset points", xytext=(0, -16), ha="center", fontsize=9, color="#0f3460", fontweight="bold")

    ax.set_xlabel("K (Top-K Retrieved)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Score", fontsize=12, fontweight="bold")
    ax.set_title("RAG Retrieval Evaluation - Recall@K & Precision@K", fontsize=14, fontweight="bold")
    ax.set_xticks(k_values)
    ax.set_ylim(-0.05, 1.1)
    ax.legend(fontsize=11, loc="center right")
    ax.grid(True, alpha=0.3, linestyle="--")
    fig.tight_layout()

    if save_path is None:
        os.makedirs(EVAL_OUTPUT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = str(EVAL_OUTPUT_DIR / f"recall_precision_k_{timestamp}.png")

    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Graph saved to: %s", save_path)
    return save_path


def save_evaluation_report(eval_results: list[dict], save_path: str | None = None) -> str:
    """Save the full evaluation report as a JSON file."""
    os.makedirs(EVAL_OUTPUT_DIR, exist_ok=True)

    if save_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = str(EVAL_OUTPUT_DIR / f"eval_report_{timestamp}.json")

    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": [
            {
                "K": r["K"],
                "recall": r["final_recall"],
                "precision": r["final_precision"],
                "num_queries": r["num_queries"],
            }
            for r in eval_results
        ],
        "detailed_logs": {f"K={r['K']}": r["query_logs"] for r in eval_results},
    }

    with open(save_path, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    logger.info("Evaluation report saved to: %s", save_path)
    return save_path


def load_eval_dataset(path: str | None = None) -> list[dict]:
    """Load the evaluation dataset from a JSON file."""
    if path is None:
        path = str(Path(__file__).resolve().parent / "eval_dataset.json")

    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    for index, item in enumerate(data):
        if "query" not in item or "expected_document_name" not in item:
            raise ValueError(f"Test data item {index} missing 'query' or 'expected_document_name': {item}")

    logger.info("Loaded %s evaluation queries from %s", len(data), path)
    return data
