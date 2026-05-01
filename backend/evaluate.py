#!/usr/bin/env python3
"""
RAG Retrieval Evaluation - CLI Entry Point
============================================

Run this script to evaluate your RAG retrieval pipeline.

Usage:
    python evaluate.py --user-id <USER_UUID> [--dataset path/to/data.json] [--k 1,3,5,10]

Before running:
    1. Make sure Ollama is running and your documents have already been indexed
    2. Edit backend/app/evaluation/eval_dataset.json with REAL document filenames
       from your indexed document set
    3. Provide a valid user_id that has uploaded documents

Example:
    python evaluate.py --user-id "abc-123-def-456" --k 1,3,5,10
"""

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.logging_utils import configure_logging  # noqa: E402
from app.evaluation.eval_runner import (  # noqa: E402
    evaluate_across_k_values,
    generate_recall_precision_graph,
    load_eval_dataset,
    save_evaluation_report,
)

configure_logging(logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate RAG retrieval quality (Recall@K & Precision@K)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--user-id",
        required=True,
        help="UUID of the user whose documents to evaluate against.",
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="Path to evaluation dataset JSON. Defaults to app/evaluation/eval_dataset.json",
    )
    parser.add_argument(
        "--k",
        default="1,3,5,10",
        help="Comma-separated K values to evaluate. Default: 1,3,5,10",
    )
    args = parser.parse_args()

    try:
        k_values = [int(x.strip()) for x in args.k.split(",")]
    except ValueError:
        logger.error("Invalid --k format. Use comma-separated integers (e.g., 1,3,5,10)")
        sys.exit(1)

    logger.info("%s", "=" * 60)
    logger.info("  RAG RETRIEVAL EVALUATION")
    logger.info("%s", "=" * 60)
    logger.info("  User ID  : %s", args.user_id)
    logger.info("  K values : %s", k_values)
    logger.info("  Dataset  : %s", args.dataset or "default (eval_dataset.json)")
    logger.info("%s", "=" * 60)

    test_data = load_eval_dataset(args.dataset)

    placeholder_count = sum(
        1 for item in test_data
        if not item.get("expected_document_name")
        or item["expected_document_name"].startswith("PUT_REAL")
    )
    if placeholder_count > 0:
        logger.warning(
            "%s/%s entries still have placeholder document names! "
            "Edit app/evaluation/eval_dataset.json with real filenames from your indexed documents.",
            placeholder_count,
            len(test_data),
        )
        proceed = input("Continue anyway? (y/N): ").strip().lower()
        if proceed != "y":
            logger.info("Aborted.")
            sys.exit(0)

    all_results = evaluate_across_k_values(
        user_id=args.user_id,
        test_data=test_data,
        k_values=k_values,
    )

    print("\n")
    print("=" * 60)
    print("  EVALUATION RESULTS SUMMARY")
    print("=" * 60)
    print(f"  {'K':<6} {'Recall@K':<14} {'Precision@K':<14} {'Queries'}")
    print("-" * 60)
    for result in all_results:
        print(
            f"  {result['K']:<6} {result['final_recall']:<14.4f} "
            f"{result['final_precision']:<14.4f} {result['num_queries']}"
        )
    print("=" * 60)

    try:
        graph_path = generate_recall_precision_graph(all_results)
        print(f"\n  Graph saved -> {graph_path}")
    except ImportError:
        print("\n  matplotlib not installed - skipping graph generation.")
        print("     Install with: pip install matplotlib")

    report_path = save_evaluation_report(all_results)
    print(f"  Report saved -> {report_path}")
    print()


if __name__ == "__main__":
    main()
