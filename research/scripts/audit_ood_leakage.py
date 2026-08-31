"""Audit persona OOD splits for identity, text, metadata, and embedding leakage."""
from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent

CHAR5_ALERT = 0.80
WORD2_ALERT = 0.80
COSINE_ALERT = 0.95


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).lower()
    return "".join(character for character in value if character.isalnum())


def _char_ngrams(text: str, n: int) -> set[str]:
    value = _normalize(text)
    return {value[index:index + n] for index in range(max(0, len(value) - n + 1))}


def _word_ngrams(text: str, n: int) -> set[tuple[str, ...]]:
    tokens = re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", text).lower(), flags=re.UNICODE)
    return {tuple(tokens[index:index + n]) for index in range(max(0, len(tokens) - n + 1))}


def _jaccard(left: set, right: set) -> float:
    union = left | right
    return len(left & right) / len(union) if union else float(left == right)


def _embedding_rows(records: list[dict], matrix: np.ndarray) -> np.ndarray:
    ids = np.asarray([int(record["id"]) for record in records])
    if ids.min() < 1 or ids.max() > len(matrix):
        raise ValueError(f"persona ids {ids.min()}..{ids.max()} exceed embedding matrix {matrix.shape}")
    return matrix[ids - 1].astype(np.float64)


def _metadata_key(record: dict, field: str):
    if field == "big_five_combo":
        return tuple(record.get("big_five", {}).get(axis) for axis in ("E", "N", "A", "C", "O"))
    if field == "preferred_actions":
        return tuple(sorted(map(int, record.get(field, []))))
    if field == "occupation_x_big_five":
        return (_metadata_key(record, "occupation"), _metadata_key(record, "big_five_combo"))
    return str(record.get(field, "")).strip().lower()


def audit_split(
    name: str,
    train: list[dict],
    test: list[dict],
    train_embeddings: np.ndarray,
    test_embeddings: np.ndarray,
) -> tuple[dict, list[dict]]:
    train_ids = {int(row["id"]) for row in train}
    test_ids = {int(row["id"]) for row in test}
    train_normalized = [_normalize(row["text"]) for row in train]
    test_normalized = [_normalize(row["text"]) for row in test]
    train_char5 = [_char_ngrams(row["text"], 5) for row in train]
    test_char5 = [_char_ngrams(row["text"], 5) for row in test]
    train_word2 = [_word_ngrams(row["text"], 2) for row in train]
    test_word2 = [_word_ngrams(row["text"], 2) for row in test]
    train_n = train_embeddings / np.maximum(np.linalg.norm(train_embeddings, axis=1, keepdims=True), 1e-12)
    test_n = test_embeddings / np.maximum(np.linalg.norm(test_embeddings, axis=1, keepdims=True), 1e-12)
    cosine = test_n @ train_n.T

    pairs = []
    for test_index, record in enumerate(test):
        exact_matches = [i for i, text in enumerate(train_normalized) if text == test_normalized[test_index]]
        char_scores = np.asarray([_jaccard(test_char5[test_index], grams) for grams in train_char5])
        word_scores = np.asarray([_jaccard(test_word2[test_index], grams) for grams in train_word2])
        char_index = int(char_scores.argmax())
        word_index = int(word_scores.argmax())
        cosine_index = int(cosine[test_index].argmax())
        pairs.append({
            "split": name,
            "test_id": int(record["id"]),
            "exact_normalized_match": bool(exact_matches),
            "exact_train_ids": ";".join(str(train[i]["id"]) for i in exact_matches),
            "char5_max_jaccard": float(char_scores[char_index]),
            "char5_train_id": int(train[char_index]["id"]),
            "word2_max_jaccard": float(word_scores[word_index]),
            "word2_train_id": int(train[word_index]["id"]),
            "embedding_max_cosine": float(cosine[test_index, cosine_index]),
            "embedding_train_id": int(train[cosine_index]["id"]),
            "test_text": record["text"],
            "nearest_embedding_text": train[cosine_index]["text"],
        })

    metadata = {}
    for field in ("occupation", "big_five_combo", "occupation_x_big_five", "preferred_actions"):
        train_values = {_metadata_key(row, field) for row in train}
        test_values = [_metadata_key(row, field) for row in test]
        metadata[field] = {
            "test_values_seen_in_train": int(sum(value in train_values for value in test_values)),
            "test_count": len(test_values),
            "fraction": float(np.mean([value in train_values for value in test_values])),
        }

    char_values = np.asarray([row["char5_max_jaccard"] for row in pairs])
    word_values = np.asarray([row["word2_max_jaccard"] for row in pairs])
    cosine_values = np.asarray([row["embedding_max_cosine"] for row in pairs])
    counts = {
        "id_overlap": len(train_ids & test_ids),
        "normalized_exact": int(sum(row["exact_normalized_match"] for row in pairs)),
        "char5_ge_0_80": int(np.sum(char_values >= CHAR5_ALERT)),
        "word2_ge_0_80": int(np.sum(word_values >= WORD2_ALERT)),
        "cosine_ge_0_95": int(np.sum(cosine_values >= COSINE_ALERT)),
    }
    gate = "fail" if any(counts[key] for key in ("id_overlap", "normalized_exact", "char5_ge_0_80", "word2_ge_0_80")) else ("warning" if counts["cosine_ge_0_95"] else "pass")
    summary = {
        "name": name,
        "n_train": len(train),
        "n_test": len(test),
        "gate": gate,
        "alert_thresholds": {"char5_jaccard": CHAR5_ALERT, "word2_jaccard": WORD2_ALERT, "embedding_cosine": COSINE_ALERT},
        "counts": counts,
        "maxima": {
            "char5_jaccard": float(char_values.max()),
            "word2_jaccard": float(word_values.max()),
            "embedding_cosine": float(cosine_values.max()),
        },
        "quantiles": {
            "char5_jaccard": {str(q): float(np.quantile(char_values, q)) for q in (0.5, 0.9, 0.95, 0.99)},
            "word2_jaccard": {str(q): float(np.quantile(word_values, q)) for q in (0.5, 0.9, 0.95, 0.99)},
            "embedding_cosine": {str(q): float(np.quantile(cosine_values, q)) for q in (0.5, 0.9, 0.95, 0.99)},
        },
        "metadata_overlap": metadata,
    }
    return summary, pairs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/ood_leakage_audit")
    args = parser.parse_args()
    data = ROOT / "data/personas"
    splits = data / "splits"
    raw300 = np.load(ROOT / "results/embeddings/persona_embeddings_300.npy")
    raw500 = np.load(REPO / "results/embeddings/persona_embeddings_500.npy")
    designer_dir = ROOT / "results/designer_persona_case_study"

    specifications = [
        ("v3_standard", data / "train_240_v3.json", data / "test_60_v3.json", raw300, None),
        ("v3_large", data / "train_400_v3.json", data / "test_100_v3.json", raw500, None),
        ("unseen_occupation_v3", splits / "unseen_occupation_v3_train.json", splits / "unseen_occupation_v3_test.json", raw300, None),
        ("unseen_archetype_v3", splits / "unseen_archetype_v3_train.json", splits / "unseen_archetype_v3_test.json", raw300, None),
        ("unseen_combo_v3", splits / "unseen_combo_v3_train.json", splits / "unseen_combo_v3_test.json", raw300, None),
        ("designer_cross_lingual", data / "train_240_v3.json", designer_dir / "designer_personas.json", raw300, np.load(designer_dir / "designer_persona_embeddings.npy")),
    ]

    summaries = []
    all_pairs = []
    for name, train_path, test_path, matrix, explicit_test_embeddings in specifications:
        train = _load(train_path)
        test = _load(test_path)
        train_embeddings = _embedding_rows(train, matrix)
        test_embeddings = explicit_test_embeddings
        if test_embeddings is None:
            test_embeddings = _embedding_rows(test, matrix)
        summary, pairs = audit_split(name, train, test, train_embeddings, test_embeddings)
        summary["train_file"] = str(train_path.relative_to(ROOT))
        summary["test_file"] = str(test_path.relative_to(ROOT) if test_path.is_relative_to(ROOT) else test_path)
        summaries.append(summary)
        all_pairs.extend(pairs)
        print(name, summary["gate"], summary["counts"], summary["maxima"])

    args.output.mkdir(parents=True, exist_ok=True)
    overall = {
        "protocol": {
            "normalization": "Unicode NFKC, lowercase, alphanumeric characters only for exact/char comparison",
            "predeclared_alerts": {"char5_jaccard": CHAR5_ALERT, "word2_jaccard": WORD2_ALERT, "embedding_cosine": COSINE_ALERT},
            "fail_rule": "any ID overlap, normalized exact match, char5>=0.80, or word2>=0.80; cosine>=0.95 alone is warning",
        },
        "overall_gate": "fail" if any(row["gate"] == "fail" for row in summaries) else ("warning" if any(row["gate"] == "warning" for row in summaries) else "pass"),
        "splits": summaries,
    }
    (args.output / "summary.json").write_text(json.dumps(overall, ensure_ascii=False, indent=2), encoding="utf-8")
    with (args.output / "nearest_pairs.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_pairs[0]))
        writer.writeheader()
        writer.writerows(all_pairs)

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))
    labels = [row["name"].replace("_v3", "").replace("_", "\n") for row in summaries]
    grouped = [[pair["char5_max_jaccard"] for pair in all_pairs if pair["split"] == row["name"]] for row in summaries]
    axes[0].boxplot(grouped, tick_labels=labels, showfliers=False)
    axes[0].axhline(CHAR5_ALERT, color="#D92D20", linestyle="--", label="Alert 0.80")
    axes[0].set_ylim(0, 1.02)
    axes[0].set_ylabel("Max train char-5 Jaccard")
    axes[0].set_title("Lexical nearest neighbor")
    axes[0].legend(frameon=False)
    grouped = [[pair["embedding_max_cosine"] for pair in all_pairs if pair["split"] == row["name"]] for row in summaries]
    axes[1].boxplot(grouped, tick_labels=labels, showfliers=False)
    axes[1].axhline(COSINE_ALERT, color="#D92D20", linestyle="--", label="Warning 0.95")
    axes[1].set_ylim(0, 1.02)
    axes[1].set_ylabel("Max train embedding cosine")
    axes[1].set_title("Semantic nearest neighbor")
    axes[1].legend(frameon=False)
    fig.suptitle("PCSP OOD persona leakage audit", fontsize=15, fontweight="bold")
    fig.tight_layout()
    fig.savefig(args.output / "ood_leakage_audit.png", dpi=180, bbox_inches="tight")
    fig.savefig(args.output / "ood_leakage_audit.svg", bbox_inches="tight")
    plt.close(fig)
    print(json.dumps({"overall_gate": overall["overall_gate"], "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
