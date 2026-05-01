# Requirements: none
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import random
from pathlib import Path
from typing import Any

from app.logging_utils import configure_logging
from rl_agent import QLearningAgent
from rl_environment import RLEnvironment
from retrieval_policy import action_config, build_state

configure_logging(logging.INFO)
logger = logging.getLogger(__name__)

DATASET_PATH = Path("eval_dataset.json")
QTABLE_PATH = Path("qtable.json")
RESULTS_DIR = Path("results")
TRAIN_METRICS_PATH = RESULTS_DIR / "rl_training.json"


def load_dataset() -> list[dict[str, Any]]:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    logger.info(
        "Loaded evaluation dataset | path=%s | records=%s",
        DATASET_PATH,
        len(dataset),
    )
    return dataset


async def resolve_expected_doc_ids(
    dataset: list[dict[str, Any]],
    session,
    user_id: str,
) -> list[dict[str, Any]]:
    """Convert expected_document_name → real document_id (UUID)
    using the existing PostgreSQL session, scoped to user_id."""
    from sqlalchemy import select

    from app.models import Document

    for record in dataset:
        filename = record.get("expected_document_name")
        if not filename:
            record["expected_doc_ids"] = []
            logger.warning("No expected_document_name in record: %s", record.get("id"))
            continue

        result = await session.execute(
            select(Document.id).where(
                Document.filename == filename,
                Document.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()

        if row:
            record["expected_doc_ids"] = [str(row)]
        else:
            record["expected_doc_ids"] = []
            logger.warning("Document not found for filename: %s (user_id=%s)", filename, user_id)

    return dataset


def save_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def summarize(variant: str, rows: list[dict[str, Any]], avg_reward: float | str) -> dict[str, Any]:
    count = max(len(rows), 1)
    return {
        "variant": variant,
        "recall_at_k": sum(row["recall_at_k"] for row in rows) / count,
        "precision_at_k": sum(row["precision_at_k"] for row in rows) / count,
        "mrr": sum(row["mrr"] for row in rows) / count,
        "hit_rate": sum(row["hit_rate"] for row in rows) / count,
        "semantic_similarity": sum(row["semantic_similarity"] for row in rows) / count,
        "avg_latency_seconds": sum(row["response_latency_seconds"] for row in rows) / count,
        "avg_reward": avg_reward,
        "latencies": [row["response_latency_seconds"] for row in rows],
        "queries": rows,
    }


async def evaluate(mode: str, user_id: str) -> dict[str, Any]:
    env = RLEnvironment(user_id)
    agent = QLearningAgent(str(QTABLE_PATH))
    dataset = load_dataset()

    from app.database import get_db

    async for session in get_db():
        dataset = await resolve_expected_doc_ids(dataset, session, user_id)
        break

    logger.info(
        "Starting evaluation | mode=%s | user_id=%s | records=%s",
        mode,
        user_id,
        len(dataset),
    )

    if mode == "rl":
        agent.epsilon = 0.0

    rows: list[dict[str, Any]] = []

    for record in dataset:
        if mode == "baseline":
            action_id = 1
        elif mode == "reranker":
            action_id = 2
        else:
            state = await build_state(user_id, record["query"])
            action_id = agent.select_action(state)

        logger.info(
            "Evaluating record | mode=%s | record_id=%s | action_id=%s",
            mode,
            record["id"],
            action_id,
        )

        result = await env.run_query(record, **action_config(action_id))
        result["action_id"] = action_id
        rows.append(result)

    avg_reward: float | str = "N/A"
    if mode == "rl" and TRAIN_METRICS_PATH.exists():
        training_metrics = json.loads(TRAIN_METRICS_PATH.read_text(encoding="utf-8"))
        avg_reward = float(training_metrics["average_reward"])

    logger.info("Completed evaluation | mode=%s | results=%s", mode, len(rows))
    return summarize(mode, rows, avg_reward)


async def train_rl(user_id: str) -> dict[str, Any]:
    env = RLEnvironment(user_id)
    agent = QLearningAgent(str(QTABLE_PATH))
    agent.qtable = {}
    agent.epsilon = 1.0

    dataset = load_dataset()

    from app.database import get_db

    async for session in get_db():
        dataset = await resolve_expected_doc_ids(dataset, session, user_id)
        break

    random.Random(7).shuffle(dataset)

    logger.info(
        "Starting RL training | user_id=%s | episodes=50 | shuffled_order=%s",
        user_id,
        [record["id"] for record in dataset],
    )

    running_total = 0.0
    rewards: list[float] = []
    cumulative_reward: list[float] = []
    action_distribution = {str(action_id): 0 for action_id in range(4)}

    for episode in range(50):
        record = dataset[episode % len(dataset)]
        state = await build_state(user_id, record["query"])
        action_id = agent.select_action(state)

        result = await env.run_query(record, **action_config(action_id))

        rewards.append(result["reward"])
        running_total += result["reward"]
        cumulative_reward.append(running_total)
        action_distribution[str(action_id)] += 1

        agent.update(state, action_id, result["reward"])
        agent.decay_epsilon()

        logger.info(
            "Training episode | episode=%s | record_id=%s | state=%s | action_id=%s | reward=%.4f | epsilon=%.4f",
            episode + 1,
            record["id"],
            state,
            action_id,
            result["reward"],
            agent.epsilon,
        )

    agent.save()

    metrics = {
        "average_reward": sum(rewards) / max(len(rewards), 1),
        "cumulative_reward": cumulative_reward,
        "action_distribution": action_distribution,
    }

    save_json(metrics, TRAIN_METRICS_PATH)

    logger.info(
        "Completed RL training | average_reward=%.4f | qtable=%s",
        metrics["average_reward"],
        QTABLE_PATH,
    )
    return metrics


def write_summary(output_path: Path) -> None:
    rows = [
        json.loads((RESULTS_DIR / f"{name}.json").read_text(encoding="utf-8"))
        for name in ("baseline", "reranker", "rl")
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "variant",
                "recall_at_k",
                "precision_at_k",
                "mrr",
                "hit_rate",
                "semantic_similarity",
                "avg_latency_seconds",
                "avg_reward",
            ]
        )

        for row in rows:
            reward_value = row["avg_reward"] if isinstance(row["avg_reward"], str) else f"{row['avg_reward']:.4f}"
            writer.writerow(
                [
                    row["variant"],
                    f"{row['recall_at_k']:.4f}",
                    f"{row['precision_at_k']:.4f}",
                    f"{row['mrr']:.4f}",
                    f"{row['hit_rate']:.4f}",
                    f"{row['semantic_similarity']:.4f}",
                    f"{row['avg_latency_seconds']:.4f}",
                    reward_value,
                ]
            )

    logger.info("Wrote summary CSV | path=%s", output_path)


def validate_args(args: argparse.Namespace) -> None:
    if args.mode != "summary" and not args.user_id:
        raise SystemExit(
            "Error: --user-id is required for baseline, reranker, train_rl, and rl modes."
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        required=True,
        choices=["baseline", "reranker", "train_rl", "rl", "summary"],
    )
    parser.add_argument(
        "--user-id",
        default="",
        help="Actual user_id that owns uploaded documents. Required for all non-summary modes.",
    )
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    validate_args(args)

    logger.info(
        "evaluation_runner invoked | mode=%s | user_id=%s | output=%s",
        args.mode,
        args.user_id or "N/A",
        args.output or "default",
    )

    if args.mode == "train_rl":
        save_json(
            asyncio.run(train_rl(args.user_id)),
            Path(args.output or TRAIN_METRICS_PATH),
        )
    elif args.mode == "summary":
        write_summary(Path(args.output or RESULTS_DIR / "summary.csv"))
    else:
        save_json(
            asyncio.run(evaluate(args.mode, args.user_id)),
            Path(args.output or RESULTS_DIR / f"{args.mode}.json"),
        )


if __name__ == "__main__":
    main()