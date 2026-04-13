"""LongMemEval benchmark dataset loader.

Downloads and loads the official LongMemEval dataset from HuggingFace.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


@dataclass
class LongMemEvalInstance:
    """Single evaluation instance from LongMemEval."""

    question_id: str
    question_type: str
    question: str
    answer: str
    haystack_sessions: list[list[dict[str, str]]]
    haystack_session_ids: list[str]
    haystack_dates: list[str]
    answer_session_ids: list[str]
    is_abstention: bool


class LongMemEvalDataset:
    """Loader for LongMemEval benchmark."""

    DATASET_URLS = {
        "small": "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_s_cleaned.json",
        "medium": "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_m_cleaned.json",
        "oracle": "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_oracle.json",
    }

    QUESTION_TYPES = [
        "single-session-user",
        "single-session-assistant",
        "single-session-preference",
        "temporal-reasoning",
        "knowledge-update",
        "multi-session",
    ]

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path("data/benchmarks/longmemeval")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._instances: dict[str, list[LongMemEvalInstance]] = {}

    def download(self, variant: str = "small") -> Path:
        """Download a variant of the dataset.

        Args:
            variant: 'small' (~115k tokens, 40 sessions), 'medium' (500 sessions),
                     or 'oracle' (only evidence sessions)

        Returns:
            Path to downloaded file
        """
        if variant not in self.DATASET_URLS:
            raise ValueError(
                f"Unknown variant: {variant}. Choose: {list(self.DATASET_URLS.keys())}"
            )

        url = self.DATASET_URLS[variant]
        output_path = self.data_dir / f"longmemeval_{variant}.json"

        if output_path.exists():
            print(f"Dataset already exists at {output_path}, skipping download")
            return output_path

        print(f"Downloading LongMemEval {variant} from HuggingFace...")
        response = requests.get(url, timeout=300)
        response.raise_for_status()

        with open(output_path, "w") as f:
            f.write(response.text)

        print(f"Downloaded to {output_path}")
        return output_path

    def load(self, variant: str = "small") -> list[LongMemEvalInstance]:
        """Load instances from a dataset variant.

        Args:
            variant: 'small', 'medium', or 'oracle'

        Returns:
            List of evaluation instances
        """
        if variant in self._instances:
            return self._instances[variant]

        cache_path = self.data_dir / f"longmemeval_{variant}.json"
        if not cache_path.exists():
            cache_path = self.download(variant)

        with open(cache_path) as f:
            raw_data = json.load(f)

        instances = []
        for item in raw_data:
            instance = self._parse_instance(item)
            instances.append(instance)

        self._instances[variant] = instances
        return instances

    def _parse_instance(self, item: dict[str, Any]) -> LongMemEvalInstance:
        """Parse a raw JSON item into a LongMemEvalInstance."""
        question_id = item["question_id"]
        is_abstention = question_id.endswith("_abs")

        return LongMemEvalInstance(
            question_id=question_id,
            question_type=item["question_type"],
            question=item["question"],
            answer=item["answer"],
            haystack_sessions=item["haystack_sessions"],
            haystack_session_ids=item["haystack_session_ids"],
            haystack_dates=item["haystack_dates"],
            answer_session_ids=item["answer_session_ids"],
            is_abstention=is_abstention,
        )

    def filter_by_type(
        self, instances: list[LongMemEvalInstance], question_type: str
    ) -> list[LongMemEvalInstance]:
        """Filter instances by question type."""
        return [i for i in instances if i.question_type == question_type]

    def filter_non_abstention(
        self, instances: list[LongMemEvalInstance]
    ) -> list[LongMemEvalInstance]:
        """Filter out abstention questions."""
        return [i for i in instances if not i.is_abstention]

    def get_stats(self, instances: list[LongMemEvalInstance]) -> dict[str, Any]:
        """Get statistics about a dataset split."""
        type_counts: dict[str, int] = {}
        abstention_count = 0
        total_sessions = 0

        for inst in instances:
            type_counts[inst.question_type] = type_counts.get(inst.question_type, 0) + 1
            if inst.is_abstention:
                abstention_count += 1
            total_sessions += len(inst.haystack_sessions)

        return {
            "total_instances": len(instances),
            "abstention_count": abstention_count,
            "answerable_count": len(instances) - abstention_count,
            "type_counts": type_counts,
            "total_sessions": total_sessions,
            "avg_sessions_per_instance": total_sessions / len(instances) if instances else 0,
        }


if __name__ == "__main__":
    dataset = LongMemEvalDataset()

    print("Downloading LongMemEval dataset...")
    path = dataset.download("small")

    print("\nLoading dataset...")
    instances = dataset.load("small")

    print(f"\nDataset loaded: {len(instances)} instances")
    stats = dataset.get_stats(instances)
    print(f"Stats: {stats}")
