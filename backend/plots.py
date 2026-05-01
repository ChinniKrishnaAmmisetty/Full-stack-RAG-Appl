# Requirements: matplotlib
import csv
import json
import matplotlib.pyplot as plt


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    with open("results/summary.csv", "r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    baseline = load_json("results/baseline.json")
    reranker = load_json("results/reranker.json")
    rl_eval = load_json("results/rl.json")
    rl_train = load_json("results/rl_training.json")
    labels = ["Baseline", "Reranker", "RL"]
    recalls = [float(row["recall_at_k"]) for row in rows]
    mrr_values = [float(row["mrr"]) for row in rows]
    latency_groups = [baseline["latencies"], reranker["latencies"], rl_eval["latencies"]]
    colors = ["#4c78a8", "#f58518", "#54a24b"]
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes[0, 0].bar([0, 1, 2], recalls, color=colors, width=0.6)
    axes[0, 0].set_xticks([0, 1, 2], labels)
    axes[0, 0].set_ylim(0, 1)
    axes[0, 0].set_title("Recall@K")
    bars = axes[0, 1].barh(labels, mrr_values, color=colors)
    axes[0, 1].set_xlim(0, 1)
    axes[0, 1].set_title("MRR")
    for bar, value in zip(bars, mrr_values):
        axes[0, 1].text(value + 0.02, bar.get_y() + (bar.get_height() / 2), f"{value:.2f}", va="center")
    axes[1, 0].boxplot(latency_groups, tick_labels=labels)
    axes[1, 0].set_title("Response latency")
    axes[1, 0].set_ylabel("seconds")
    axes[1, 1].plot(range(1, 51), rl_train["cumulative_reward"], label="RL agent", color="#54a24b")
    axes[1, 1].set_title("RL cumulative reward")
    axes[1, 1].set_xlabel("episode number")
    axes[1, 1].set_ylabel("cumulative reward")
    axes[1, 1].legend()
    fig.suptitle("RAG System Comparison: Baseline vs Reranker vs RL")
    fig.tight_layout()
    fig.savefig("results/comparison.png", dpi=150)


if __name__ == "__main__":
    main()
