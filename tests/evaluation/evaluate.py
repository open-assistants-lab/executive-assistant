"""Agent evaluation framework - runs persona interactions and captures metrics."""

import asyncio
import json
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from tests.evaluation.personas import PERSONAS, generate_test_queries, get_persona


@dataclass
class InteractionResult:
    """Result of a single interaction."""

    persona_id: str
    query: str
    response: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_errors: list[str] = field(default_factory=list)
    duration_ms: int = 0
    success: bool = False
    error: str | None = None
    context_maintained: bool = True
    hallucinated: bool = False
    topic_switch_detected: bool = False


@dataclass
class PersonaEvaluationResult:
    """Evaluation result for a persona."""

    persona_id: str
    persona_name: str
    total_interactions: int
    successful_interactions: int
    failed_interactions: int
    total_tool_calls: int
    tool_errors: int
    avg_duration_ms: float
    context_maintained_count: int
    hallucination_count: int
    topic_switch_issues: int
    accuracy_score: float
    interactions: list[InteractionResult] = field(default_factory=list)


class AgentEvaluator:
    """Evaluates agent with different personas."""

    def __init__(self, user_id: str = "eval_user", output_dir: str = "data/evaluations"):
        self.user_id = user_id
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def run_single_interaction(
        self,
        persona: dict,
        query: str,
        run_agent_fn,
    ) -> InteractionResult:
        """Run a single interaction with the agent."""
        start_time = time.time()

        try:
            langgraph_messages = [HumanMessage(content=query)]

            result = await run_agent_fn(
                user_id=self.user_id,
                messages=langgraph_messages,
                message=query,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            messages = result.get("messages", [])
            tool_calls = []
            response_text = ""

            for msg in messages:
                msg_type = getattr(msg, "type", None)

                if msg_type == "tool":
                    content = getattr(msg, "content", None)
                    if content:
                        tool_calls.append({"type": "tool", "content": content})

                elif msg_type == "ai":
                    content = getattr(msg, "content", "")
                    tool_calls_list = getattr(msg, "tool_calls", None)
                    if tool_calls_list:
                        for tc in tool_calls_list:
                            tool_calls.append(
                                {
                                    "type": "tool_call",
                                    "name": tc.get("name", "unknown"),
                                    "args": tc.get("args", {}),
                                }
                            )
                    if content:
                        response_text = content

            success = len(tool_calls) > 0 or response_text.strip() != ""

            return InteractionResult(
                persona_id=persona["id"],
                query=query,
                response=response_text,
                tool_calls=tool_calls,
                duration_ms=duration_ms,
                success=success,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return InteractionResult(
                persona_id=persona["id"],
                query=query,
                response="",
                duration_ms=duration_ms,
                success=False,
                error=str(e),
            )

    async def evaluate_persona(
        self,
        persona: dict,
        num_interactions: int,
        run_agent_fn,
    ) -> PersonaEvaluationResult:
        """Evaluate agent with a specific persona."""
        queries = generate_test_queries(persona, num_interactions)

        interactions = []
        total_tool_calls = 0
        total_tool_errors = 0
        context_maintained = 0
        hallucinations = 0
        topic_switches = 0

        for i, query in enumerate(queries):
            print(f"  [{i + 1}/{num_interactions}] {query[:50]}...")

            result = await self.run_single_interaction(persona, query, run_agent_fn)
            interactions.append(result)

            total_tool_calls += len(result.tool_calls)
            total_tool_errors += len(result.tool_errors)

            if result.success:
                context_maintained += 1

            if result.hallucinated:
                hallucinations += 1

            if result.topic_switch_detected:
                topic_switches += 1

            await asyncio.sleep(0.1)

        successful = sum(1 for i in interactions if i.success)
        failed = len(interactions) - successful
        accuracy = (successful / len(interactions)) * 100 if interactions else 0

        return PersonaEvaluationResult(
            persona_id=persona["id"],
            persona_name=persona["name"],
            total_interactions=len(interactions),
            successful_interactions=successful,
            failed_interactions=failed,
            total_tool_calls=total_tool_calls,
            tool_errors=total_tool_errors,
            avg_duration_ms=sum(i.duration_ms for i in interactions) / len(interactions)
            if interactions
            else 0,
            context_maintained_count=context_maintained,
            hallucination_count=hallucinations,
            topic_switch_issues=topic_switches,
            accuracy_score=accuracy,
            interactions=interactions,
        )

    async def run_evaluation(
        self,
        run_agent_fn,
        num_interactions: int = 100,
        persona_ids: list[str] | None = None,
    ) -> list[PersonaEvaluationResult]:
        """Run evaluation across all or selected personas."""
        if persona_ids:
            personas = [p for p in PERSONAS if p["id"] in persona_ids]
        else:
            personas = PERSONAS

        results = []

        for persona in personas:
            print(f"\n{'=' * 60}")
            print(f"Evaluating: {persona['name']} ({persona['style']})")
            print(f"{'=' * 60}")

            result = await self.evaluate_persona(persona, num_interactions, run_agent_fn)
            results.append(result)

            self._save_result(result)

        return results

    def _save_result(self, result: PersonaEvaluationResult):
        """Save evaluation result to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{result.persona_id}_{timestamp}.json"
        filepath = self.output_dir / filename

        data = {
            "persona_id": result.persona_id,
            "persona_name": result.persona_name,
            "total_interactions": result.total_interactions,
            "successful_interactions": result.successful_interactions,
            "failed_interactions": result.failed_interactions,
            "total_tool_calls": result.total_tool_calls,
            "tool_errors": result.tool_errors,
            "avg_duration_ms": result.avg_duration_ms,
            "context_maintained_count": result.context_maintained_count,
            "hallucination_count": result.hallucination_count,
            "topic_switch_issues": result.topic_switch_issues,
            "accuracy_score": result.accuracy_score,
            "interactions": [
                {
                    "query": i.query,
                    "response": i.response[:500] if i.response else "",
                    "tool_calls": i.tool_calls,
                    "duration_ms": i.duration_ms,
                    "success": i.success,
                    "error": i.error,
                }
                for i in result.interactions
            ],
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        print(f"  Saved to {filepath}")

    def generate_summary_report(self, results: list[PersonaEvaluationResult]) -> str:
        """Generate a summary report of all evaluations."""
        report = []
        report.append("=" * 80)
        report.append("AGENT EVALUATION SUMMARY REPORT")
        report.append("=" * 80)
        report.append("")

        total_interactions = sum(r.total_interactions for r in results)
        total_successful = sum(r.successful_interactions for r in results)
        total_tool_calls = sum(r.total_tool_calls for r in results)
        total_tool_errors = sum(r.tool_errors for r in results)
        overall_accuracy = (
            (total_successful / total_interactions) * 100 if total_interactions else 0
        )

        report.append(f"Total Interactions: {total_interactions}")
        report.append(f"Successful: {total_successful} ({overall_accuracy:.1f}%)")
        report.append(f"Failed: {total_interactions - total_successful}")
        report.append(f"Total Tool Calls: {total_tool_calls}")
        report.append(f"Tool Errors: {total_tool_errors}")
        report.append("")

        report.append("-" * 80)
        report.append("PERSONA BREAKDOWN")
        report.append("-" * 80)

        for r in results:
            report.append(f"\n{r.persona_name} ({r.persona_id}):")
            report.append(f"  Accuracy: {r.accuracy_score:.1f}%")
            report.append(f"  Tool Calls: {r.total_tool_calls}, Errors: {r.tool_errors}")
            report.append(f"  Avg Duration: {r.avg_duration_ms:.0f}ms")
            report.append(
                f"  Context Maintained: {r.context_maintained_count}/{r.total_interactions}"
            )
            report.append(f"  Hallucinations: {r.hallucination_count}")
            report.append(f"  Topic Switch Issues: {r.topic_switch_issues}")

        report.append("")
        report.append("-" * 80)
        report.append("ISSUES TO INVESTIGATE")
        report.append("-" * 80)

        for r in results:
            if r.tool_errors > r.total_tool_calls * 0.1:
                report.append(
                    f"  {r.persona_name}: High tool error rate ({r.tool_errors}/{r.total_tool_calls})"
                )

            if r.hallucination_count > 0:
                report.append(
                    f"  {r.persona_name}: {r.hallucination_count} hallucination(s) detected"
                )

            if r.topic_switch_issues > r.total_interactions * 0.1:
                report.append(
                    f"  {r.persona_name}: Topic switch issues ({r.topic_switch_issues}/{r.total_interactions})"
                )

        return "\n".join(report)


async def main():
    """Run evaluation."""
    from src.agents.manager import run_agent

    evaluator = AgentEvaluator(user_id="eval_user")

    print("Starting persona evaluation...")
    print(f"Personas: {len(PERSONAS)}")
    print(f"Interactions per persona: 100")
    print(f"Total: {len(PERSONAS) * 100} interactions")
    print("")

    results = await evaluator.run_evaluation(
        run_agent_fn=run_agent,
        num_interactions=100,
    )

    report = evaluator.generate_summary_report(results)
    print("\n" + report)

    summary_path = evaluator.output_dir / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(summary_path, "w") as f:
        f.write(report)
    print(f"\nSummary saved to {summary_path}")


if __name__ == "__main__":
    asyncio.run(main())
