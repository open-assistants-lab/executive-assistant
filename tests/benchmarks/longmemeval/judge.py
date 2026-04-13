"""LongMemEval judge module.

Evaluates agent answers against expected answers using GPT-4o as judge,
following the official LongMemEval evaluation methodology.
"""

import os
from typing import Any

from openai import AsyncOpenAI


class Judge:
    """Judge that compares agent answers to expected answers using GPT-4o.

    This follows the official LongMemEval evaluation which uses GPT-4o as judge
    to determine if the agent's answer is correct.
    """

    SYSTEM_PROMPT = """You are an expert judge evaluating the accuracy of answers to questions.
Your task is to determine if the predicted answer is semantically equivalent to the expected answer.

For each evaluation, you will receive:
- A question
- The expected (ground truth) answer
- The predicted (agent's) answer

Your evaluation criteria:
1. The predicted answer must contain the key information from the expected answer
2. Minor wording differences are acceptable if the meaning is preserved
3. Partial credit may be given if the answer contains some correct information
4. For abstention questions (where no answer should be given), the correct response is to say nothing or indicate no information

Respond with your evaluation in this format:
{
    "is_correct": true/false,
    "reasoning": "Brief explanation of your evaluation"
}
"""

    USER_PROMPT_TEMPLATE = """Question: {question}

Expected Answer: {expected_answer}

Predicted Answer: {predicted_answer}

Evaluate whether the predicted answer is correct. Consider:
- Does it contain the same key information as the expected answer?
- Are there any factual errors?
- Is it incomplete or partially correct?

Respond in the specified JSON format."""

    def __init__(self, model: str = "gpt-4o"):
        self.model = model
        self.client = AsyncOpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            organization=os.environ.get("OPENAI_ORGANIZATION"),
        )

    async def evaluate(
        self,
        question: str,
        expected_answer: str,
        predicted_answer: str,
    ) -> dict[str, Any]:
        """Evaluate a single answer.

        Args:
            question: The original question
            expected_answer: The ground truth answer
            predicted_answer: The agent's predicted answer

        Returns:
            Dictionary with is_correct and reasoning
        """
        user_prompt = self.USER_PROMPT_TEMPLATE.format(
            question=question,
            expected_answer=expected_answer,
            predicted_answer=predicted_answer,
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )

        result_text = response.choices[0].message.content or ""

        import json

        try:
            result: dict[str, Any] = json.loads(result_text)
            return result
        except json.JSONDecodeError:
            return {
                "is_correct": False,
                "reasoning": f"Failed to parse judge response: {result_text}",
            }

    async def evaluate_batch(
        self,
        evaluations: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        """Evaluate multiple answers in batch.

        Args:
            evaluations: List of dicts with question, expected_answer, predicted_answer

        Returns:
            List of evaluation results
        """
        import asyncio

        tasks = [
            self.evaluate(
                eval["question"],
                eval["expected_answer"],
                eval["predicted_answer"],
            )
            for eval in evaluations
        ]

        return await asyncio.gather(*tasks)


class ExactMatchJudge:
    """Simple exact match judge for when GPT-4o is not available.

    This provides a fallback evaluation method using exact string matching
    or simple keyword overlap.
    """

    def evaluate(
        self,
        question: str,
        expected_answer: str,
        predicted_answer: str,
    ) -> dict[str, Any]:
        """Evaluate using exact match or keyword overlap."""
        expected_lower = expected_answer.lower().strip()
        predicted_lower = predicted_answer.lower().strip()

        if expected_lower == predicted_lower:
            return {"is_correct": True, "reasoning": "Exact match"}

        expected_words = set(expected_lower.split())
        predicted_words = set(predicted_lower.split())

        overlap = expected_words & predicted_words

        if overlap == expected_words:
            return {"is_correct": True, "reasoning": "All expected words present"}

        if overlap:
            overlap_ratio = len(overlap) / len(expected_words)
            if overlap_ratio >= 0.8:
                return {
                    "is_correct": True,
                    "reasoning": f"High keyword overlap ({overlap_ratio:.0%})",
                }
            elif overlap_ratio >= 0.5:
                return {
                    "is_correct": False,
                    "reasoning": f"Partial keyword overlap ({overlap_ratio:.0%})",
                }

        return {"is_correct": False, "reasoning": "No meaningful match"}


async def judge_results(
    results: list[dict[str, Any]],
    use_gpt4o: bool = True,
) -> list[dict[str, Any]]:
    """Judge a list of evaluation results.

    Args:
        results: List of dicts with question_id, question, expected_answer, agent_answer
        use_gpt4o: Whether to use GPT-4o judge (requires API key)

    Returns:
        List of results with is_correct and judge_reasoning added
    """
    judge: Judge | ExactMatchJudge
    if use_gpt4o and os.environ.get("OPENAI_API_KEY"):
        judge = Judge()
    else:
        judge = ExactMatchJudge()

    judged_results = []

    for result in results:
        if result.get("error"):
            result["is_correct"] = None
            result["judge_reasoning"] = f"Skipped due to error: {result['error']}"
            judged_results.append(result)
            continue

        if isinstance(judge, ExactMatchJudge):
            evaluation = judge.evaluate(
                question=result["question"],
                expected_answer=result["expected_answer"],
                predicted_answer=result["agent_answer"],
            )
        else:
            evaluation = await judge.evaluate(
                question=result["question"],
                expected_answer=result["expected_answer"],
                predicted_answer=result["agent_answer"],
            )

        result["is_correct"] = evaluation.get("is_correct")
        result["judge_reasoning"] = evaluation.get("reasoning")
        judged_results.append(result)

    return judged_results
