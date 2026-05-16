# MemoryAgentBench (MAB) Integration Plan

## Overview

**MemoryAgentBench (MAB)** is a benchmark from UCSD that evaluates LLM agents across four core memory competencies: accurate retrieval, test-time learning, long-range understanding, and selective forgetting. Unlike LongMemEval and LoCoMo (which focus on retrieval from static histories), MAB uses **active, incremental multi-turn interactions** where the agent must learn, update, and forget information over the course of a session.

**Paper:** [2507.05257](https://arxiv.org/abs/2507.05257) | **Repo:** [HUST-AI-HYZ/MemoryAgentBench](https://github.com/HUST-AI-HYZ/MemoryAgentBench) | **Dataset:** [ai-hyz/MemoryAgentBench](https://huggingface.co/datasets/ai-hyz/MemoryAgentBench)

---

## Why MAB

| Dimension | LongMemEval | LoCoMo | MAB |
|-----------|-------------|--------|-----|
| Interaction style | One-shot: answer question from history | One-shot: QA/summarize/dialogue from past | **Interactive**: multi-turn learning & updating |
| Memory competency | Retrieval only | Retrieval + synthesis | **Retrieval + learning + understanding + forgetting** |
| Key unique test | Search precision in noise | Long-range temporal synthesis | **Test-time knowledge acquisition & selective forgetting** |
| Our system stress test | HybridDB search quality | Summarization + extraction at scale | **Confidence lifecycle, fact supersession, correction handling** |

MAB uniquely tests:
- **Test-time learning**: Can the agent acquire new facts mid-session and use them correctly?
- **Selective forgetting**: Can the agent forget outdated/corrected info while retaining current facts?
- **Long-range understanding**: Can the agent connect facts across distant turns?

These directly map to our **confidence lifecycle** (decay, boost, auto-deletion), **fact supersession** (structured upserts), **correction handling** (keyword detection → re-extraction), and **consolidation** (contradiction detection).

---

## File Structure

```
tests/benchmarks/mab/
├── __init__.py
├── PLAN.md              # This file
├── dataset.py           # MABDataset — download/load/parse from HuggingFace
├── adapter.py           # MABAdapter — feed sessions as interactive conversations
├── runner.py            # MABRunner — run interactive multi-turn evaluations
├── judge.py             # Judge — GPT-4o scoring per competency
├── eval.py              # Main evaluation entry point
└── cli.py               # Click CLI

data/benchmarks/mab/
├── mab_raw/             # Raw dataset files from HuggingFace
├── sessions/            # Intermediate session state dumps (for debugging)
└── results/             # Benchmark result JSON files
```

---

## Phase 1: Dataset (`dataset.py`)

### Four Competency Splits
MAB has four sub-benchmarks, each testing a distinct memory competency:

| Split | Description | Example |
|-------|-------------|---------|
| **Accurate Retrieval** | Multi-turn conversation; later turns ask about early facts | Turn 3: "I live in Denver" → Turn 50: "Where do I live?" |
| **Test-Time Learning** | New facts introduced mid-session; must be learned & used | Turn 10: "I just started learning Rust" → Turn 15: "What language are you learning?" |
| **Long-Range Understanding** | Connect facts across widely separated turns; synthesize | Turn 5: "My flight is at 3pm" → Turn 80: "My meeting ends at 1pm" → "How much time between?" |
| **Selective Forgetting** | Facts are updated/corrected; old version must be forgotten | Turn 20: "I moved to SF" → Turn 60: "I actually live in NY now" → "Where do I live?" (should answer NY, not SF) |

### Data Format (expected)
Based on the paper, each instance is a multi-turn conversation with checkpoints:
```json
{
  "instance_id": "mab_retrieval_001",
  "competency": "accurate_retrieval",
  "turns": [
    {"role": "user", "content": "I live in Denver and work at Google."},
    {"role": "assistant", "content": "Got it, Denver and Google."},
    {"role": "user", "content": "I enjoy hiking on weekends."},
    ...
    {"role": "user", "content": "Remind me — where do I live and work?"},
  ],
  "checkpoints": {
    "turn_5":  {"questions": [{"q": "Where does the user live?", "a": "Denver"}]},
    "turn_10": {"questions": [{"q": "...", "a": "..."}]},
    "turn_final": {"questions": [{"q": "Where does the user live?", "a": "Denver"}]}
  },
  "metrics": ["retrieval_accuracy", "learning_rate", "forgetting_rate"]
}
```

### Implementation

```python
# dataset.py
@dataclass
class MABInstance:
    instance_id: str
    competency: Literal["accurate_retrieval", "test_time_learning", 
                         "long_range_understanding", "selective_forgetting"]
    turns: list[dict[str, str]]           # Conversation turns
    checkpoints: dict[str, dict]          # Questions at each checkpoint
    answer: str                           # Final expected answer

class MABDataset:
    HF_REPO = "ai-hyz/MemoryAgentBench"
    
    def download(self) -> Path:
        """Download dataset from HuggingFace."""
    
    def load(self, competency: str | None = None) -> list[MABInstance]:
        """Load instances, optionally filtered by competency."""
    
    def get_stats(self) -> dict:
        """Per-competency counts, avg turn lengths, etc."""
```

### Dependencies
- Same pattern as LoCoMo: prefer `datasets` library, fall back to raw HF downloads

---

## Phase 2: Adapter (`adapter.py`)

### Key Design Decisions

Unlike LongMemEval and LoCoMo where we pre-inject all history, MAB requires **incremental, interactive processing**:

1. **Feed turns one at a time** to the agent, simulating a real conversation
2. **MemoryMiddleware extracts facts** after each batch of turns (every 3 turns, per EXTRACTION_TURN_INTERVAL)
3. **Checkpoints test retrieval** at specific turn boundaries — we pause conversation, ask the test question, score the answer, then resume

### Implementation

```python
# adapter.py
from src.sdk.agents import AgentLoop
from src.sdk.runner import create_sdk_loop, reset_sdk_loop
from src.sdk.messages import Message

class MABAdapter:
    """Adapter that feeds MAB turns through our agent incrementally.
    
    This is different from the LongMemEval/LoCoMo adapter pattern because
    MAB tests active learning, not retrieval from pre-injected history.
    """
    
    def __init__(self, user_id: str = "benchmark_mab"):
        self.user_id = user_id
        self.loop: AgentLoop | None = None
        self.conversation_history: list[Message] = []
    
    async def initialize(self) -> None:
        """Create a fresh AgentLoop with MemoryMiddleware enabled."""
        self.loop = await create_sdk_loop(self.user_id)
    
    async def feed_turns(
        self,
        turns: list[dict[str, str]],
        stop_before: int | None = None,
    ) -> None:
        """Feed conversation turns into the agent.
        
        If stop_before is set, feed turns up to but not including that index.
        The agent processes each turn through the full middleware pipeline.
        
        This is where MemoryMiddleware actually extracts facts and
        builds up the memory store incrementally.
        """
    
    async def checkpoint_test(
        self,
        checkpoint_id: str,
        questions: list[dict[str, str]],
    ) -> list[dict]:
        """Run checkpoint questions against current memory state.
        
        Sends each question as a new turn, captures agent response,
        returns results with agent answers.
        
        This does NOT modify the conversation history used for
        subsequent turn feeding — it's a read-only snapshot.
        """
    
    def get_memory_snapshot(self) -> dict:
        """Capture current state of all extracted memories.
        
        Useful for debugging: what facts have been learned so far?
        What's the confidence distribution?
        """
    
    async def teardown(self) -> None:
        """Clean up: reset loop, clear conversation store."""
        reset_sdk_loop(self.user_id)
```

### Critical: Checkpoint Isolation
Checkpoint questions must **not** pollute the conversation history for subsequent turns. Use a temporary copy of messages or a separate `run_single()` call with the checkpoint question + prior conversation context.

```python
async def checkpoint_test(self, checkpoint_id: str, questions: list[dict]) -> list[dict]:
    """Read-only checkpoint test."""
    results = []
    for q in questions:
        # Run as a fresh single-turn query, with memory tools available
        result = await self.loop.run_single(
            message=Message.user(
                f"Based on your memory of our conversation, {q['q']}\n"
                f"User ID: {self.user_id}"
            )
        )
        results.append({
            "checkpoint_id": checkpoint_id,
            "question": q["q"],
            "expected": q["a"],
            "agent_answer": result  # extract content from Message
        })
    return results
```

---

## Phase 3: Runner (`runner.py`)

### Interactive Evaluation Loop

```python
# runner.py
@dataclass
class MABCheckpointResult:
    checkpoint_id: str
    turn_number: int
    questions: list[dict]               # Question + expected + agent_answer + is_correct

@dataclass 
class MABInstanceResult:
    instance_id: str
    competency: str
    checkpoint_results: list[MABCheckpointResult]
    final_memory_snapshot: dict | None   # All extracted memories at end
    latency_total_ms: float
    error: str | None = None

class MABRunner:
    def __init__(self, user_id: str = "benchmark_mab"):
        self.adapter = MABAdapter(user_id=user_id)
    
    async def evaluate_instance(
        self,
        instance: MABInstance,
    ) -> MABInstanceResult:
        """Evaluate a single MAB instance.
        
        Algorithm:
        1. Initialize fresh AgentLoop
        2. Iterate through turns, stopping at each checkpoint
        3. At each checkpoint, pause and run test questions
        4. Resume conversation turns
        5. After final checkpoint, capture memory snapshot
        6. Clean up
        
        Special handling for selective_forgetting:
        - After a "correction" turn, also check that the
          MemoryStore has superseded the old fact (not just
          that the agent answers correctly).
        """
    
    async def run_competency(
        self,
        instances: list[MABInstance],
        competency: str,
        max_instances: int | None = None,
        rate_limit_rpm: int = 30,
    ) -> list[MABInstanceResult]:
        """Run all instances for a single competency."""
    
    async def run_full_benchmark(
        self,
        competencies: list[str] | None = None,
        max_per_competency: int | None = None,
    ) -> dict[str, list[MABInstanceResult]]:
        """Run all competencies, returning results grouped by type."""
```

### Interactive Loop Pseudocode

```
for each instance:
    adapter.initialize()           # Fresh AgentLoop + MemoryMiddleware
    for turn_idx, turn in enumerate(instance.turns):
        if turn_idx is a checkpoint:
            pause()
            test_questions = adapter.checkpoint_test(checkpoint_id, questions)
            store checkpoint results
            resume()
        adapter.feed_turn(turn)    # Process through agent (extracts memories)
    
    memory_snapshot = adapter.get_memory_snapshot()
    adapter.teardown()
```

### Specialized Handling per Competency

```python
# runner.py
class MABRunner:
    async def _handle_selective_forgetting(
        self,
        instance: MABInstance,
        adapter: MABAdapter,
    ) -> dict:
        """After selective_forgetting instances, verify MemoryStore state.
        
        Check that:
        - Old fact is superseded (superseded_by is not None)
        - New fact has higher confidence
        - Correction connection exists between old and new
        - Agent correctly answers with NEW fact, not old
        """
        snapshot = adapter.get_memory_snapshot()
        # Query MemoryStore directly for fact history
        ...
        return {
            "old_fact_superseded": bool,
            "correction_connection_exists": bool,
            "agent_used_new_fact": bool,
        }
```

---

## Phase 4: Judging (`judge.py`)

### Scoring per Competency

MAB defines four metrics:

| Competency | Metric | Definition | Method |
|-----------|--------|------------|--------|
| Accurate Retrieval | Retrieval Accuracy | % of checkpoint questions answered correctly | GPT-4o semantic equivalence |
| Test-Time Learning | Learning Rate | % of newly introduced facts correctly recalled | GPT-4o |
| Long-Range Understanding | Temporal Reasoning Accuracy | % of multi-fact synthesis questions correct | GPT-4o |
| Selective Forgetting | Forgetting Rate | % of updated facts where old version is NOT repeated | GPT-4o + MemoryStore audit |

### Implementation

```python
# judge.py
class MABJudge:
    def __init__(self):
        self.qa_judge = Judge(model="gpt-4o-mini")  # Reuse LongMemEval Judge
    
    async def judge_checkpoint_question(
        self,
        question: str,
        expected_answer: str,
        agent_answer: str,
    ) -> dict[str, Any]:
        """Judge a single checkpoint question answer."""
        return await self.qa_judge.evaluate(question, expected_answer, agent_answer)
    
    async def judge_instance(
        self,
        result: MABInstanceResult,
    ) -> MABInstanceResult:
        """Judge all checkpoint questions in an instance.
        
        Per-competency aggregation:
        - retrieval: accuracy = correct/total
        - learning: learning_rate = correct/total (only for turns after fact was introduced)
        - understanding: accuracy on synthesis questions
        - forgetting: forgetting_rate = (old_answers_correctly_rejected)/(total_updates)
        """
```

### Automated Memory Store Audit (Selective Forgetting Only)

```python
def audit_memory_store_forgetting(
    instance: MABInstance,
    memory_snapshot: dict,
) -> dict:
    """Verify MemoryStore integrity for selective_forgetting instances.
    
    Returns:
        - superseded_count: How many old facts were correctly superseded
        - orphan_count: Old facts remaining but should be superseded
        - correction_connections: How many correction edges exist
        - confidence_progression: Old→new confidence trajectory
    """
```

This is the **unique value** of MAB for our system — it validates not just answer correctness but also the internal state of our memory store.

---

## Phase 5: Main Runner (`eval.py`)

```python
# eval.py
@dataclass
class MABBenchmarkResults:
    variant: str
    model: str
    timestamp: str
    by_competency: dict[str, list[MABInstanceResult]]
    
    def retrieval_accuracy(self) -> float:
        """Overall accurate retrieval accuracy."""
    
    def learning_rate(self) -> float:
        """Overall test-time learning rate."""
    
    def understanding_accuracy(self) -> float:
        """Overall long-range understanding accuracy."""
    
    def forgetting_rate(self) -> float:
        """Overall selective forgetting rate."""
    
    def memory_store_integrity(self) -> dict:
        """MemoryStore audit results (supersession, confidence, corrections)."""
    
    def to_dict(self) -> dict:
        """Full serializable results."""


async def run_benchmark(
    competencies: list[str] | None = None,
    max_per: int | None = None,
    use_gpt4o: bool = True,
    output_path: Path | None = None,
    audit_memory_store: bool = True,  # Unique to MAB
) -> MABBenchmarkResults:
    """Run MAB benchmark.
    
    If audit_memory_store=True (default), also validates:
    - Fact supersession correctness
    - Confidence lifecycle behavior
    - Correction connection graph integrity
    """
```

### CLI

```python
@click.group()
def cli():
    """MemoryAgentBench runner."""

@cli.command()
@click.option("--competency", multiple=True)
@click.option("--max", type=int)
@click.option("--output", type=click.Path(path_type=Path))
@click.option("--no-audit", is_flag=True, help="Skip MemoryStore integrity audit")
def run(competency, max, output, no_audit):
    """Run MAB benchmark."""

@cli.command()
def download():
    """Download MAB dataset."""

@cli.command()
def inspect():
    """Show dataset stats and sample instances."""
```

---

## Phase 6: What It Tests of Our System

| Our Component | What MAB Validates |
|---------------|-------------------|
| **MemoryMiddleware._extract_with_llm** | Correctly extracts facts from mid-conversation turns; handles new info in real time |
| **MemoryMiddleware._should_extract** | New-info keyword detection triggers extraction at right moments |
| **MemoryStore.upsert_fact_memory** | Entity-attribute-value structured upsert correctly supersedes old values |
| **MemoryStore.add_memory confidence lifecycle** | Re-observation boosts (+0.05), decay works, deletion at < 0.1 |
| **MemoryStore.supercede_memory** | Corrections correctly mark old facts superseded |
| **MemoryStore connections ("corrects")** | Correction edges created between old and new facts |
| **Consolidation.contradiction_detection** | Finds and resolves contradictions between corrected facts |
| **memory_search / memory_get_history** | Agent effectively uses tools to retrieve current (not outdated) facts |
| **Progressive disclosure (working memory)** | Working memory correctly surfaces current facts, not superseded ones |
| **MEMORY_TYPE_CORRECTION handling** | Corrections detected from keywords + properly routed to upsert |

### Unique MAB Tests Not Covered by Other Benchmarks

| Test | LongMemEval | LoCoMo | MAB |
|------|:---:|:---:|:---:|
| Pre-injected history retrieval | ✓ | ✓ | – |
| Active mid-session fact learning | – | – | ✓ |
| Correction → fact supersession | – | – | ✓ |
| Confidence boost on re-observation | – | – | ✓ |
| Decay of unused facts | – | – | ✓ |
| Auto-deletion of stale facts | – | – | ✓ |
| MemoryStore graph integrity audit | – | – | ✓ |
| Test-time knowledge acquisition | – | – | ✓ |

---

## Implementation Order

1. **`dataset.py`** — Download, parse, validate MAB data; understand exact checkpoint format
2. **`adapter.py`** — The most complex piece: interactive turn feeding with checkpoint pauses
3. **`runner.py`** — Instance evaluation loop with per-competency specialization
4. **`judge.py`** — GPT-4o QA judging + MemoryStore audit functions
5. **`eval.py` + `cli.py`** — Full benchmark runner
6. **Integration tests** — Test that a single instance completes correctly
7. **MemoryStore audit validation** — Verify that selective_forgetting audit catches regressions
8. **CI integration** — Optional: smaller subset in CI for fast feedback

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| MAB not yet on HuggingFace (paper is from 2025, code may be repo-based) | Contact authors; if dataset is repo-only, implement direct git-based loading |
| Interactive mode exposes race conditions in our middleware | Run single-threaded, sequential turns; add explicit `await` between turns |
| Checkpoint testing is slow (new LLM call per checkpoint) | Batch checkpoint questions into single AgentLoop.run_single() calls |
| MemoryStore audit adds complexity | Make it optional (--no-audit flag); start with answer-only judging |
| Long conversations cause SummarizationMiddleware to fire mid-benchmark | Disable summarization during MAB runs; test full context handling separately |
| Selective forgetting instances may be ambiguous | Use structured MemoryStore queries (not just agent responses) for ground truth |

---

## Success Criteria

- [ ] Per-competency accuracy/rate measured and comparable to MAB paper baselines
- [ ] Selective forgetting audit confirms:
  - [ ] Old facts correctly superseded
  - [ ] New facts have higher confidence
  - [ ] "corrects" connections exist
  - [ ] Agent never returns old (superseded) facts as truth
- [ ] Test-time learning: facts extracted from mid-conversation turns are retrievable
- [ ] MemoryStore confidence lifecycle functions as designed (boost, decay, delete)
- [ ] No cross-instance memory contamination
- [ ] Results reproducible: `uv run python -m tests.benchmarks.mab.eval`
- [ ] All benchmark-specific tests pass
