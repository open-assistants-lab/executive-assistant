"""LongMemEval evaluation runner.

This module handles the evaluation loop:
1. For each question instance, inject history into ConversationStore
2. Run our agent with the question
3. Collect the agent's response
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.agents.manager import run_agent

from .adapter import LongMemEvalAdapter
from .dataset import LongMemEvalInstance


@dataclass
class EvaluationResult:
    """Result of evaluating a single question."""

    question_id: str
    question_type: str
    question: str
    expected_answer: str
    agent_answer: str
    is_correct: bool | None = None
    judge_reasoning: str | None = None
    latency_ms: float = 0.0
    error: str | None = None


@dataclass
class EvaluationRun:
    """Results from a complete evaluation run."""

    dataset_variant: str
    total_questions: int
    answered_correctly: int = 0
    abstention_questions: int = 0
    errors: int = 0
    results: list[EvaluationResult] = field(default_factory=list)
    duration_seconds: float = 0.0

    def accuracy(self) -> float:
        """Calculate accuracy (excluding abstention questions)."""
        answerable = self.total_questions - self.abstention_questions
        if answerable == 0:
            return 0.0
        return self.answered_correctly / answerable

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "dataset_variant": self.dataset_variant,
            "total_questions": self.total_questions,
            "answered_correctly": self.answered_correctly,
            "abstention_questions": self.abstention_questions,
            "errors": self.errors,
            "accuracy": self.accuracy(),
            "duration_seconds": self.duration_seconds,
            "results": [
                {
                    "question_id": r.question_id,
                    "question_type": r.question_type,
                    "question": r.question,
                    "expected_answer": r.expected_answer,
                    "agent_answer": r.agent_answer,
                    "is_correct": r.is_correct,
                    "judge_reasoning": r.judge_reasoning,
                    "latency_ms": r.latency_ms,
                    "error": r.error,
                }
                for r in self.results
            ],
        }


class LongMemEvalRunner:
    """Runs LongMemEval evaluation against our agent.

    This tests our agent's memory retrieval + reasoning on the LongMemEval benchmark.
    For QA mode, we:
    1. Inject all session history into our ConversationStore
    2. Ask the question via our agent (which uses memory tools)
    3. Compare agent answer to expected answer
    """

    def __init__(
        self,
        user_id: str = "benchmark",
        agent_user_id: str = "benchmark",
        skip_abstention: bool = True,
        max_context_chars: int = 100000,
    ):
        self.adapter = LongMemEvalAdapter(user_id=user_id)
        self.agent_user_id = agent_user_id
        self.skip_abstention = skip_abstention
        self.max_context_chars = max_context_chars

    async def evaluate_instance(
        self,
        instance: LongMemEvalInstance,
        use_direct_context: bool = False,
    ) -> EvaluationResult:
        """Evaluate a single LongMemEval instance.

        Args:
            instance: The question to evaluate
            use_direct_context: If True, inject history and use our memory tools.
                               If False, provide context directly in the prompt.

        Returns:
            EvaluationResult with agent's answer
        """
        start_time = time.time()

        try:
            if use_direct_context:
                return await self._evaluate_with_direct_context(instance, start_time)
            else:
                return await self._evaluate_with_memory_tools(instance, start_time)

        except Exception as e:
            return EvaluationResult(
                question_id=instance.question_id,
                question_type=instance.question_type,
                question=instance.question,
                expected_answer=instance.answer,
                agent_answer="",
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000,
            )

    async def _evaluate_with_memory_tools(
        self,
        instance: LongMemEvalInstance,
        start_time: float,
    ) -> EvaluationResult:
        """Evaluate using our memory tools (the real test).

        This injects sessions into ConversationStore and lets our agent
        use memory_get_history, memory_search, etc. to answer.
        """
        self.adapter.inject_sessions(
            instance.haystack_sessions,
            instance.haystack_dates,
        )

        messages = [{"role": "user", "content": instance.question}]

        result = await run_agent(
            user_id=self.agent_user_id,
            messages=messages,
            message=instance.question,
        )

        agent_answer = self._extract_answer(result)

        return EvaluationResult(
            question_id=instance.question_id,
            question_type=instance.question_type,
            question=instance.question,
            expected_answer=instance.answer,
            agent_answer=agent_answer,
            latency_ms=(time.time() - start_time) * 1000,
        )

    async def _evaluate_with_direct_context(
        self,
        instance: LongMemEvalInstance,
        start_time: float,
    ) -> EvaluationResult:
        """Evaluate by providing context directly (baseline comparison).

        This bypasses our memory system and provides the full context
        directly to the agent for answering.
        """
        from .adapter import format_sessions_as_context

        context = format_sessions_as_context(
            instance.haystack_sessions,
            instance.haystack_dates,
            format_type="natural",
            max_context_chars=self.max_context_chars,
        )

        prompt = f"""Based on the following conversation history, answer the question.

=== CONVERSATION HISTORY ===
{context}

=== QUESTION ===
{instance.question}

Provide a direct answer to the question based only on the conversation history above."""

        messages = [{"role": "user", "content": prompt}]

        result = await run_agent(
            user_id=self.agent_user_id,
            messages=messages,
            message=prompt,
        )

        agent_answer = self._extract_answer(result)

        return EvaluationResult(
            question_id=instance.question_id,
            question_type=instance.question_type,
            question=instance.question,
            expected_answer=instance.answer,
            agent_answer=agent_answer,
            latency_ms=(time.time() - start_time) * 1000,
        )

    def _extract_answer(self, result: dict[str, Any]) -> str:
        """Extract the final answer from agent result."""
        if isinstance(result, dict):
            if "messages" in result:
                messages = result["messages"]
                if messages and len(messages) > 0:
                    last_msg = messages[-1]
                    if hasattr(last_msg, "content"):
                        return last_msg.content
                    if isinstance(last_msg, dict) and "content" in last_msg:
                        return last_msg["content"]
        return str(result)

    async def run_evaluation(
        self,
        instances: list[LongMemEvalInstance],
        use_direct_context: bool = False,
        max_instances: int | None = None,
        rate_limit_rpm: int = 60,
    ) -> EvaluationRun:
        """Run evaluation on a list of instances.

        Args:
            instances: List of LongMemEval instances to evaluate
            use_direct_context: Use direct context (baseline) vs memory tools (real test)
            max_instances: Limit number of instances to evaluate
            rate_limit_rpm: Rate limit for API calls

        Returns:
            EvaluationRun with all results
        """
        if max_instances:
            instances = instances[:max_instances]

        total = len(instances)
        abstention_count = sum(1 for i in instances if i.is_abstention and self.skip_abstention)
        answerable = total - abstention_count

        print(
            f"Running evaluation on {total} instances ({answerable} answerable, {abstention_count} abstention)"
        )
        print(
            f"Mode: {'direct context (baseline)' if use_direct_context else 'memory tools (real test)'}"
        )
        print()

        results: list[EvaluationResult] = []
        errors = 0
        start = time.time()

        rate_limit_delay = 60.0 / rate_limit_rpm if rate_limit_rpm > 0 else 0

        for idx, instance in enumerate(instances):
            if self.skip_abstention and instance.is_abstention:
                continue

            if idx % 10 == 0:
                print(f"Progress: {idx}/{total} ({idx / total * 100:.1f}%)")

            result = await self.evaluate_instance(instance, use_direct_context)
            results.append(result)

            if result.error:
                errors += 1

            if rate_limit_delay > 0 and idx < total - 1:
                await asyncio.sleep(rate_limit_delay)

        duration = time.time() - start

        answered_correctly = sum(1 for r in results if r.is_correct)

        return EvaluationRun(
            dataset_variant="longmemeval_s",
            total_questions=total,
            answered_correctly=answered_correctly,
            abstention_questions=abstention_count,
            errors=errors,
            results=results,
            duration_seconds=duration,
        )


async def run_benchmark(
    variant: str = "small",
    max_instances: int | None = None,
    use_direct_context: bool = False,
    output_path: Path | None = None,
) -> EvaluationRun:
    """Convenience function to run a complete benchmark.

    Args:
        variant: Dataset variant ('small', 'medium', or 'oracle')
        max_instances: Limit instances to evaluate
        use_direct_context: Use direct context instead of memory tools
        output_path: Path to save results JSON

    Returns:
        EvaluationRun with results
    """
    from .dataset import LongMemEvalDataset

    dataset = LongMemEvalDataset()
    print(f"Loading LongMemEval {variant}...")
    instances = dataset.load(variant)

    if max_instances:
        instances = instances[:max_instances]

    runner = LongMemEvalRunner(
        user_id="benchmark",
        agent_user_id="benchmark",
        skip_abstention=True,
    )

    print(f"Evaluating {len(instances)} instances...")
    results = await runner.run_evaluation(
        instances,
        use_direct_context=use_direct_context,
    )

    print("\n=== RESULTS ===")
    print(f"Accuracy: {results.accuracy():.2%}")
    print(
        f"Correct: {results.answered_correctly}/{results.total_questions - results.abstention_questions}"
    )
    print(f"Errors: {results.errors}")
    print(f"Duration: {results.duration_seconds:.1f}s")

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results.to_dict(), f, indent=2)
        print(f"\nResults saved to {output_path}")

    return results
