# Strategic Compaction Plan

## Executive Summary

Strategic compaction is a technique to preserve critical conversation state during summarization, preventing data loss and enabling context recovery. This plan outlines two implementation approaches: prompt-based (quick win) and middleware-based (robust solution).

**Current Problem**: When the `SummarizationMiddleware` triggers at 10,000 tokens and compacts to 2,000 tokens, we lose:
- Active conversation state
- Pending task context
- User preferences expressed mid-conversation
- References to files/tables/threads being worked on

**Proposed Solution**: Extract and preserve a structured "checkpoint" of recoverable state before summarization occurs.

---

## Part 1: Background & Context

### Current Summarization Setup

**Location**: `src/executive_assistant/agent/langchain_agent.py:118-166`

**Configuration**:
```python
# Current thresholds
MW_SUMMARIZATION_MAX_TOKENS = 10_000  # Trigger threshold
MW_SUMMARIZATION_TARGET_TOKENS = 2_000  # Keep after summarization
Ratio: 5:1
```

**Current Prompt** (lines 135-155):
```python
summary_prompt = """Summarize the conversation below into 200-300 words maximum.

Focus on:
1. User's goal/intent
2. Key decisions made
3. Outstanding tasks or next steps
4. Important constraints or preferences

Exclude:
- Tool call details, errors, or retries
- Raw tool outputs or logs
- Debug or system/internal details
- Middleware events

CRITICAL: Keep summary under 300 words. Be concise.

<messages>
{messages}
</messages>

Respond ONLY with the summary. No additional text."""
```

**What Happens**:
1. Middleware checks token count on every message
2. When count >= 10,000 → trigger summarization
3. LLM condenses conversation to 200-300 words
4. Keep last 2,000 tokens of messages (~15-20 messages)
5. Older messages are discarded

**What Gets Lost**:
- In-flight task context (e.g., "working on table X")
- File IDs/database names referenced earlier
- User's stated preferences for current session
- Active workflow state (multi-step processes)
- Important but subtle constraints mentioned once

### Why Strategic Compaction?

**From everything-claude-code**:
> Pre-compaction hooks save important context before summarization triggers, maintaining "checkpoint" state for verification and recovery.

**Benefits**:
1. **Context Recovery**: Restore critical state after summarization
2. **Better Continuity**: Agent doesn't "forget" active work
3. **Improved UX**: No need for user to repeat context
4. **Verification**: Checkpoint enables testing of summarization quality

---

## Part 2: Design Approaches

### Approach A: Prompt-Based Enhancement (Quick Win)

**Concept**: Extend the summary prompt to include structured state extraction.

**Pros**:
- ✅ No code changes to middleware
- ✅ Fast to implement (1-2 hours)
- ✅ Easy to test and iterate
- ✅ Works with existing LangChain middleware

**Cons**:
- ❌ Extracts from LARGE context (after trigger fires)
- ❌ LLM may miss subtle state cues
- ❌ No pre-summarization hook
- ❌ Can't prevent data loss, only mitigate

**Implementation**:
```python
summary_prompt = """Summarize the conversation below into 200-300 words maximum.

Focus on:
1. User's goal/intent
2. Key decisions made
3. Outstanding tasks or next steps
4. Important constraints or preferences

Exclude:
- Tool call details, errors, or retries
- Raw tool outputs or logs
- Debug or system/internal details
- Middleware events

---

## STATE CHECKPOINT (for context recovery)

After the summary, extract a JSON checkpoint with recoverable state:

```json
{
  "active_goals": ["goal1", "goal2"],
  "pending_tasks": [
    {"task": "Complete CRM database schema", "context": "Using PostgreSQL"},
    {"task": "Add validation to user input", "context": "In auth_flow"}
  ],
  "key_decisions": {
    "storage": "Use PostgreSQL for main database",
    "auth": "Implement JWT tokens"
  },
  "user_preferences": {
    "format": "Prefer JSON for data export",
    "verbosity": "Concise responses, skip details"
  },
  "context_references": {
    "files": ["schema.sql", "auth.py"],
    "tables": ["users", "sessions"],
    "databases": ["crm_db"],
    "threads": ["telegram:123456"]
  },
  "workflow_state": {
    "current_step": "Implementing user registration",
    "completed_steps": ["Schema design", "Database setup"],
    "next_steps": ["Add email validation", "Create password reset flow"]
  }
}
```

**Checkpoint Rules**:
- Only include fields with relevant values
- Omit empty arrays/objects
- Keep IDs and names concrete (no vague references)
- Preserve user's explicit statements verbatim when possible

---

CRITICAL: Keep summary under 300 words. Be concise.

<messages>
{messages}
</messages>

Respond with:
[SUMMARY]
...200-300 word summary...

[CHECKPOINT]
{"active_goals": [...], ...}
"""
```

**Output Parsing**:
```python
# Post-processing to extract checkpoint
import re

def parse_summary_with_checkpoint(response: str) -> tuple[str, dict]:
    """Parse LLM response into summary and checkpoint."""

    # Extract summary
    summary_match = re.search(r'\[SUMMARY\](.*?)\[CHECKPOINT\]', response, re.DOTALL)
    summary = summary_match.group(1).strip() if summary_match else response

    # Extract checkpoint JSON
    checkpoint_match = re.search(r'\[CHECKPOINT\](.*?)$', response, re.DOTALL)
    checkpoint = {}
    if checkpoint_match:
        try:
            checkpoint = json.loads(checkpoint_match.group(1).strip())
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse checkpoint JSON: {checkpoint_match.group(1)}")

    return summary, checkpoint
```

**Storage of Checkpoint**:
```python
# Store in thread-specific location
checkpoint_path = settings.get_thread_root(thread_id) / "checkpoints" / f"{timestamp}.json"
checkpoint_path.write_text(json.dumps(checkpoint, indent=2))

# Most recent checkpoint is always accessible
latest_checkpoint_path = settings.get_thread_root(thread_id) / "checkpoints" / "latest.json"
latest_checkpoint_path.write_text(json.dumps(checkpoint, indent=2))
```

---

### Approach B: Custom Middleware (Robust Solution)

**Concept**: Create a pre-summarization middleware that extracts state BEFORE the trigger fires.

**Pros**:
- ✅ Extracts state at optimal time (80% of threshold)
- ✅ Can analyze full context before truncation
- ✅ More reliable extraction
- ✅ Enables "prevention" vs "recovery"

**Cons**:
- ❌ Requires custom middleware code
- ❌ More complex to implement (2-3 days)
- ❌ Needs thorough testing
- ❌ Adds another layer to middleware stack

**Architecture**:
```python
# src/executive_assistant/agent/strategic_compaction.py

from langchain.agents.middleware import Middleware
from executive_assistant.config.settings import settings

class PreSummarizationCheckpointMiddleware(Middleware):
    """Extract checkpoint state before summarization triggers."""

    def __init__(self, checkpoint_threshold_ratio: float = 0.8):
        """
        Args:
            checkpoint_threshold_ratio: Extract checkpoint when context
                reaches this ratio of summarization threshold.
                Default: 0.8 (80% of max_tokens)
        """
        self.checkpoint_threshold_ratio = checkpoint_threshold_ratio
        self._last_checkpoint_token_count = 0

    async def __call__(self, agent, input):
        """
        Process input and extract checkpoint before summarization.

        Args:
            agent: Next middleware/agent in chain
            input: Input data (messages + metadata)

        Returns:
            Agent output
        """
        from executive_assistant.storage.thread_storage import get_thread_id

        # Count tokens in current input
        token_count = self._count_tokens(input)

        # Calculate checkpoint threshold
        checkpoint_threshold = (
            settings.MW_SUMMARIZATION_MAX_TOKENS * self.checkpoint_threshold_ratio
        )

        # Extract checkpoint if we're at threshold and haven't recently
        thread_id = get_thread_id()

        if token_count >= checkpoint_threshold:
            # Only extract if we've added significant tokens since last checkpoint
            tokens_since_last_checkpoint = token_count - self._last_checkpoint_token_count

            if tokens_since_last_checkpoint >= 1000:  # Minimum delta to re-checkpoint
                logger.info(
                    f"[PreSummarization] Token count {token_count} >= "
                    f"checkpoint threshold {checkpoint_threshold:.0f}, "
                    f"extracting checkpoint for thread {thread_id}"
                )

                # Extract and save checkpoint
                checkpoint = await self._extract_checkpoint(input, thread_id)
                await self._save_checkpoint(thread_id, checkpoint)

                self._last_checkpoint_token_count = token_count

        # Pass to next middleware/agent
        return await agent.ainvoke(input)

    def _count_tokens(self, input) -> int:
        """Count tokens in input messages."""
        # Reuse existing token counter
        from langchain.agents.middleware.token_counter import count_tokens
        return count_tokens(input["messages"])

    async def _extract_checkpoint(self, input, thread_id: str) -> dict:
        """Extract structured checkpoint from conversation context."""

        messages = input["messages"]

        # Build extraction prompt
        extraction_prompt = f"""Analyze this conversation and extract a structured checkpoint for context recovery.

<messages>
{self._format_messages(messages)}
</messages>

Extract and return ONLY a JSON object with this schema:
{{
  "active_goals": ["string"],  // What the user is currently trying to accomplish
  "pending_tasks": [{{"task": "string", "context": "string"}}],  // In-flight work
  "key_decisions": {{"topic": "decision"}},  // Decisions made
  "user_preferences": {{"domain": "preference"}},  // User's stated preferences
  "context_references": {{"files": [], "tables": [], "databases": [], "threads": []}},  // IDs and names
  "workflow_state": {{"current_step": "string", "completed_steps": [], "next_steps": []}}  // Active workflows
}}

IMPORTANT:
- Only include fields with relevant values
- Extract concrete IDs/names (not vague references)
- Preserve user's exact phrasing for preferences
- Omit empty arrays/objects
- Return ONLY the JSON, no additional text
"""

        # Use fast LLM for extraction (lower cost, faster)
        from executive_assistant.llm import get_llm

        fast_llm = get_llm(provider=settings.MEM_EXTRACT_PROVIDER, model=settings.MEM_EXTRACT_MODEL)

        try:
            response = await fast_llm.ainvoke(extraction_prompt)

            # Parse JSON response
            import json
            import re

            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                response = json_match.group(1)
            else:
                # Try to find raw JSON object
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    response = json_match.group(1)

            checkpoint = json.loads(response)

            # Add metadata
            checkpoint["metadata"] = {
                "extracted_at": datetime.now().isoformat(),
                "token_count": self._count_tokens(input),
                "thread_id": thread_id
            }

            return checkpoint

        except Exception as e:
            logger.error(f"[PreSummarization] Failed to extract checkpoint: {e}")
            # Return empty checkpoint on failure
            return {
                "metadata": {
                    "extracted_at": datetime.now().isoformat(),
                    "token_count": self._count_tokens(input),
                    "thread_id": thread_id,
                    "extraction_error": str(e)
                }
            }

    async def _save_checkpoint(self, thread_id: str, checkpoint: dict):
        """Save checkpoint to thread-specific storage."""

        from executive_assistant.config.settings import settings
        import json
from pathlib import Path

        # Ensure checkpoints directory exists
        checkpoints_dir = settings.get_thread_root(thread_id) / "checkpoints"
        checkpoints_dir.mkdir(parents=True, exist_ok=True)

        # Save timestamped checkpoint
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        checkpoint_file = checkpoints_dir / f"checkpoint_{timestamp}.json"
        checkpoint_file.write_text(json.dumps(checkpoint, indent=2))

        # Save as "latest" for easy access
        latest_file = checkpoints_dir / "latest.json"
        latest_file.write_text(json.dumps(checkpoint, indent=2))

        # Keep only last 10 checkpoints to save space
        self._cleanup_old_checkpoints(checkpoints_dir, keep=10)

        logger.info(f"[PreSummarization] Checkpoint saved to {checkpoint_file}")

    def _cleanup_old_checkpoints(self, checkpoints_dir: Path, keep: int = 10):
        """Remove old checkpoints, keeping only the most recent N."""

        checkpoints = sorted(
            checkpoints_dir.glob("checkpoint_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        # Remove all but the N most recent
        for old_checkpoint in checkpoints[keep:]:
            old_checkpoint.unlink()
            logger.debug(f"[PreSummarization] Removed old checkpoint: {old_checkpoint}")

    def _format_messages(self, messages) -> str:
        """Format messages for extraction prompt."""
        formatted = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            formatted.append(f"{role.upper()}: {content}")
        return "\n\n".join(formatted)
```

**Integration into Agent**:
```python
# In src/executive_assistant/agent/langchain_agent.py

# Add before SummarizationMiddleware
if settings.MW_STRATEGIC_COMPRESSION_ENABLED:
    from executive_assistant.agent.strategic_compaction import PreSummarizationCheckpointMiddleware

    middleware.append(
        PreSummarizationCheckpointMiddleware(
            checkpoint_threshold_ratio=0.8  # Extract at 80% of threshold
        )
    )

if settings.MW_SUMMARIZATION_ENABLED:
    # ... existing SummarizationMiddleware configuration
```

**Configuration**:
```python
# In docker/config.yaml
middleware:
  strategic_compaction:
    enabled: true
    checkpoint_threshold_ratio: 0.8  # 0.0-1.0, default 0.8

# In src/executive_assistant/config/settings.py
MW_STRATEGIC_COMPRESSION_ENABLED: bool = _yaml_field(
    "MIDDLEWARE_STRATEGIC_COMPRESSION_ENABLED", True
)
MW_STRATEGIC_COMPRESSION_THRESHOLD_RATIO: float = _yaml_field(
    "MIDDLEWARE_STRATEGIC_COMPRESSION_THRESHOLD_RATIO", 0.8
)
```

---

## Part 3: Checkpoint Usage & Recovery

### Storage Structure

```
data/users/{thread_id}/
├── checkpoints/
│   ├── checkpoint_20260131_143022.json    # Timestamped checkpoints
│   ├── checkpoint_20260131_150845.json
│   ├── latest.json                         # Always most recent
│   └── .checkpoint_index                   # Optional: index for faster lookup
└── ...
```

### Checkpoint Schema

```json
{
  "active_goals": [
    "Build CRM system for franchise tracking",
    "Implement user authentication flow"
  ],
  "pending_tasks": [
    {
      "task": "Create franchisees table",
      "context": "PostgreSQL, need fields: name, contact, territory"
    },
    {
      "task": "Add email validation to registration",
      "context": "Using regex pattern, currently in auth.py"
    }
  ],
  "key_decisions": {
    "database": "PostgreSQL for main data store",
    "cache": "Redis for session management",
    "auth": "JWT tokens with 7-day expiry"
  },
  "user_preferences": {
    "response_style": "concise",
    "code_format": "include type hints",
    "test_framework": "pytest"
  },
  "context_references": {
    "files": ["schema.sql", "auth.py", "routes.py"],
    "tables": ["franchisees", "users", "sessions"],
    "databases": ["crm_db"],
    "threads": ["telegram:123456"],
    "external_apis": ["stripe", "sendgrid"]
  },
  "workflow_state": {
    "current_step": "Creating database migration scripts",
    "completed_steps": [
      "Schema design",
      "Database setup",
      "User authentication"
    ],
    "next_steps": [
      "Create franchisees table",
      "Build admin dashboard",
      "Add CSV import for franchise data"
    ]
  },
  "metadata": {
    "extracted_at": "2026-01-31T14:30:22Z",
    "token_count": 8247,
    "thread_id": "telegram:123456",
    "summarization_imminent": true
  }
}
```

### Recovery: Injecting Checkpoint into Context

**When to inject**:
1. After summarization occurs
2. When user returns after long absence
3. When agent appears "lost" or confused

**Integration into System Prompt**:
```python
# In src/executive_assistant/channels/base.py or prompts.py

async def load_checkpoint_into_context(thread_id: str) -> str:
    """Load latest checkpoint and format for system prompt."""

    from pathlib import Path
    from executive_assistant.config.settings import settings

    checkpoint_path = settings.get_thread_root(thread_id) / "checkpoints" / "latest.json"

    if not checkpoint_path.exists():
        return ""

    try:
        checkpoint = json.loads(checkpoint_path.read_text())

        # Format checkpoint as readable context
        context = "\n## Active Context Checkpoint\n\n"

        if checkpoint.get("active_goals"):
            context += "**Active Goals**:\n"
            for goal in checkpoint["active_goals"]:
                context += f"- {goal}\n"
            context += "\n"

        if checkpoint.get("pending_tasks"):
            context += "**Pending Tasks**:\n"
            for task in checkpoint["pending_tasks"]:
                context += f"- **{task['task']}**"
                if task.get("context"):
                    context += f" ({task['context']})"
                context += "\n"
            context += "\n"

        if checkpoint.get("key_decisions"):
            context += "**Key Decisions**:\n"
            for topic, decision in checkpoint["key_decisions"].items():
                context += f"- **{topic}**: {decision}\n"
            context += "\n"

        if checkpoint.get("user_preferences"):
            context += "**User Preferences**:\n"
            for domain, pref in checkpoint["user_preferences"].items():
                context += f"- **{domain}**: {pref}\n"
            context += "\n"

        if checkpoint.get("context_references"):
            refs = checkpoint["context_references"]
            any_refs = any(refs.values())  # Check if not all empty
            if any_refs:
                context += "**Context References**:\n"
                if refs.get("files"):
                    context += f"- Files: {', '.join(refs['files'])}\n"
                if refs.get("tables"):
                    context += f"- Tables: {', '.join(refs['tables'])}\n"
                if refs.get("databases"):
                    context += f"- Databases: {', '.join(refs['databases'])}\n"
                context += "\n"

        if checkpoint.get("workflow_state"):
            ws = checkpoint["workflow_state"]
            context += "**Workflow State**:\n"
            if ws.get("current_step"):
                context += f"- Currently: {ws['current_step']}\n"
            if ws.get("completed_steps"):
                context += f"- Completed: {', '.join(ws['completed_steps'])}\n"
            if ws.get("next_steps"):
                context += f"- Next: {', '.join(ws['next_steps'])}\n"
            context += "\n"

        context += f"*Checkpoint extracted at {checkpoint.get('metadata', {}).get('extracted_at', 'unknown')}*\n"

        return context

    except Exception as e:
        logger.error(f"Failed to load checkpoint for {thread_id}: {e}")
        return ""

# In system prompt assembly
async def get_system_prompt(thread_id: str = None) -> str:
    """Build system prompt with checkpoint injection."""

    base_prompt = _load_base_prompt()

    # Inject checkpoint if available
    if thread_id:
        checkpoint_context = await load_checkpoint_into_context(thread_id)
        if checkpoint_context:
            base_prompt += "\n" + checkpoint_context

    return base_prompt
```

---

## Part 4: Implementation Plan

### Phase 1: Prompt-Based Approach (Week 1, Days 1-2)

**Goal**: Quick win to test the concept.

#### Day 1: Implementation
- [ ] Update `summary_prompt` in `langchain_agent.py`
- [ ] Add checkpoint JSON schema to prompt
- [ ] Implement `parse_summary_with_checkpoint()` function
- [ ] Add checkpoint storage to `data/users/{thread_id}/checkpoints/`

#### Day 2: Testing
- [ ] Create test conversation that triggers summarization
- [ ] Verify checkpoint extraction works
- [ ] Validate JSON parsing
- [ ] Check checkpoint storage location
- [ ] Test checkpoint recovery (manual)

**Success Criteria**:
- Checkpoint extracted and saved when summarization triggers
- JSON parses without errors
- Checkpoint file created in correct location
- At least 3 checkpoint fields populated (goals, tasks, decisions)

---

### Phase 2: Custom Middleware (Week 1-2)

**Goal**: Robust pre-summarization checkpoint extraction.

#### Day 3-4: Middleware Implementation
- [ ] Create `src/executive_assistant/agent/strategic_compaction.py`
- [ ] Implement `PreSummarizationCheckpointMiddleware` class
- [ ] Add token counting logic
- [ ] Implement checkpoint extraction (use fast LLM)
- [ ] Add checkpoint storage with cleanup
- [ ] Write unit tests for extraction

#### Day 5: Integration
- [ ] Add configuration to `settings.py`
- [ ] Add to config.yaml
- [ ] Integrate into middleware stack (before SummarizationMiddleware)
- [ ] Test with sample conversation

#### Day 6-7: Testing & Refinement
- [ ] Test extraction at various token counts (8k, 9k, 10k)
- [ ] Verify checkpoint quality (manual inspection)
- [ ] Test concurrent conversations (multiple threads)
- [ ] Benchmark performance (latency impact)
- [ ] Handle edge cases (malformed JSON, LLM failures)

**Success Criteria**:
- Checkpoint extracted at 80% of threshold (8,000 tokens)
- No significant latency increase (<500ms)
- Graceful degradation on extraction failures
- Works across multiple concurrent threads

---

### Phase 3: Checkpoint Recovery (Week 2)

**Goal**: Make checkpoints useful for context recovery.

#### Day 8-9: Injection Logic
- [ ] Implement `load_checkpoint_into_context()` function
- [ ] Add checkpoint formatting for readability
- [ ] Integrate into `get_system_prompt()`
- [ ] Test checkpoint injection after summarization

#### Day 10: Verification
- [ ] Create test scenario: long conversation → summarization → follow-up
- [ ] Verify agent remembers context from checkpoint
- [ ] Test with user: "Continue where we left off"
- [ ] Compare with/without checkpoint

**Success Criteria**:
- Agent correctly recalls active goals after summarization
- Agent references previously mentioned files/tables
- User doesn't need to repeat context
- Seamless conversation continuity

---

### Phase 4: Polish & Documentation (Week 2, Days 11-14)

**Goal**: Production-ready implementation.

#### Day 11: Management Commands
- [ ] Add `/checkpoint show` - display current checkpoint
- [ ] Add `/checkpoint clear` - delete checkpoints
- [ ] Add `/checkpoint test` - trigger manual extraction

#### Day 12: Monitoring
- [ ] Add logging for checkpoint events
- [ ] Track extraction success/failure rate
- [ ] Monitor checkpoint file sizes
- [ ] Alert on repeated extraction failures

#### Day 13: Documentation
- [ ] Update README with checkpoint feature
- [ ] Document checkpoint schema
- [ ] Add usage examples
- [ ] Create troubleshooting guide

#### Day 14: Final Testing
- [ ] End-to-end integration test
- [ ] Load test (100+ concurrent conversations)
- [ ] Verify checkpoint cleanup works
- [ ] Check for memory leaks

---

## Part 5: Testing Strategy

### Unit Tests

```python
# tests/test_strategic_compaction.py

import pytest
from executive_assistant.agent.strategic_compaction import (
    PreSummarizationCheckpointMiddleware,
    parse_summary_with_checkpoint
)

class TestCheckpointExtraction:
    """Test checkpoint extraction logic."""

    def test_parse_summary_with_checkpoint_valid(self):
        """Test parsing valid summary + checkpoint response."""
        response = """[SUMMARY]
User is building a CRM system. Decided on PostgreSQL. Working on schema.

[CHECKPOINT]
{"active_goals": ["Build CRM"], "pending_tasks": [{"task": "Create schema", "context": "PostgreSQL"}]}
"""
        summary, checkpoint = parse_summary_with_checkpoint(response)

        assert "CRM system" in summary
        assert checkpoint["active_goals"] == ["Build CRM"]
        assert len(checkpoint["pending_tasks"]) == 1

    def test_parse_summary_with_checkpoint_malformed_json(self):
        """Test handling of malformed JSON in checkpoint."""
        response = """[SUMMARY]
User is building a CRM.

[CHECKPOINT]
{invalid json}
"""
        summary, checkpoint = parse_summary_with_checkpoint(response)

        assert "CRM" in summary
        assert checkpoint == {}

    def test_parse_summary_without_checkpoint(self):
        """Test parsing summary without checkpoint section."""
        response = "User is building a CRM system."
        summary, checkpoint = parse_summary_with_checkpoint(response)

        assert "CRM" in summary
        assert checkpoint == {}


class TestPreSummarizationMiddleware:
    """Test middleware logic."""

    @pytest.mark.asyncio
    async def test_checkpoint_at_threshold(self):
        """Test checkpoint extraction at threshold."""
        middleware = PreSummarizationCheckpointMiddleware(
            checkpoint_threshold_ratio=0.8
        )

        # Mock input with 8000 tokens (80% of 10000)
        input_data = {
            "messages": [{"role": "user", "content": "x" * 30000}]  # ~8000 tokens
        }

        # Should trigger extraction
        with patch.object(middleware, '_extract_checkpoint') as mock_extract:
            await middleware(agent=Mock(), input=input_data)
            mock_extract.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_checkpoint_below_threshold(self):
        """Test no extraction below threshold."""
        middleware = PreSummarizationCheckpointMiddleware(
            checkpoint_threshold_ratio=0.8
        )

        # Mock input with 5000 tokens
        input_data = {
            "messages": [{"role": "user", "content": "x" * 15000}]
        }

        # Should NOT trigger extraction
        with patch.object(middleware, '_extract_checkpoint') as mock_extract:
            await middleware(agent=Mock(), input=input_data)
            mock_extract.assert_not_called()
```

### Integration Tests

```python
# tests/integration/test_checkpoint_recovery.py

import pytest
from executive_assistant.agent.langchain_agent import create_agent
from executive_assistant.storage.thread_storage import set_thread_id

@pytest.mark.asyncio
async def test_checkpoint_recovery_after_summarization():
    """Test that checkpoint enables context recovery after summarization."""

    # Set thread context
    thread_id = "test:checkpoint_recovery"
    set_thread_id(thread_id)

    # Create agent with strategic compaction
    agent = create_agent(thread_id=thread_id)

    # Phase 1: Build up context (create files, tables, etc.)
    await agent.ainvoke({
        "messages": [
            {"role": "user", "content": "I'm building a CRM system with PostgreSQL. Let's create a franchisees table with columns: id, name, email, territory, created_at."}
        ]
    })

    # Phase 2: Continue until near threshold (simulate with many messages)
    for i in range(50):
        await agent.ainvoke({
            "messages": [
                {"role": "user", "content": f"Add more details about feature {i}"}
            ]
        })

    # Checkpoint should have been extracted
    from pathlib import Path
    from executive_assistant.config.settings import settings

    checkpoint_path = settings.get_thread_root(thread_id) / "checkpoints" / "latest.json"
    assert checkpoint_path.exists(), "Checkpoint file should exist"

    checkpoint = json.loads(checkpoint_path.read_text())
    assert "CRM" in str(checkpoint["active_goals"])
    assert any("franchisees" in t["task"].lower() for t in checkpoint.get("pending_tasks", []))

    # Phase 3: Trigger summarization (add more messages)
    for i in range(50):
        await agent.ainvoke({
            "messages": [
                {"role": "user", "content": f"Additional context {i}"}
            ]
        })

    # Phase 4: Test recovery - ask about context from before summarization
    response = await agent.ainvoke({
        "messages": [
            {"role": "user", "content": "What columns did we decide on for the franchisees table?"}
        ]
    })

    # Agent should remember the context
    assert "franchisees" in response["messages"][-1]["content"].lower()
    assert any(col in response["messages"][-1]["content"].lower() for col in ["name", "email", "territory"])


@pytest.mark.asyncio
async def test_checkpoint_injection_in_system_prompt():
    """Test that checkpoint is injected into system prompt."""

    thread_id = "test:checkpoint_injection"
    set_thread_id(thread_id)

    # Create a checkpoint manually
    from executive_assistant.config.settings import settings
    import json

    checkpoint = {
        "active_goals": ["Test goal"],
        "pending_tasks": [{"task": "Test task", "context": "Test context"}],
        "metadata": {"extracted_at": "2026-01-31T10:00:00Z"}
    }

    checkpoint_path = settings.get_thread_root(thread_id) / "checkpoints" / "latest.json"
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(json.dumps(checkpoint))

    # Load system prompt
    from executive_assistant.prompts import get_system_prompt

    system_prompt = await get_system_prompt(thread_id)

    # Verify checkpoint is in prompt
    assert "Active Context Checkpoint" in system_prompt
    assert "Test goal" in system_prompt
    assert "Test task" in system_prompt
```

### Manual Testing Checklist

- [ ] Create long conversation (>10k tokens)
- [ ] Verify checkpoint extracted at 8k tokens
- [ ] Check checkpoint file content is accurate
- [ ] Verify summarization triggers at 10k tokens
- [ ] After summarization, ask about context from before
- [ ] Verify agent remembers checkpointed information
- [ ] Test with multiple concurrent users
- [ ] Verify checkpoints don't leak between threads
- [ ] Test checkpoint cleanup (old files removed)
- [ ] Verify performance impact is minimal

---

## Part 6: Success Metrics

### Quantitative Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Extraction Success Rate** | >95% | (successful extractions / total triggers) |
| **Latency Impact** | <500ms | Average time added per message |
| **Checkpoint Quality** | >80% fields populated | Manual inspection of 20 checkpoints |
| **Recovery Accuracy** | >90% | Agent correctly recalls checkpointed info |
| **Storage Overhead** | <1MB/user | Average checkpoint storage per user |
| **File Cleanup** | <10 files/user | Old checkpoints properly removed |

### Qualitative Metrics

- User reports fewer repetitions of context
- Conversations feel more continuous after summarization
- Agent doesn't "forget" active work
- No user complaints about lost context

---

## Part 7: Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **LLM extraction fails** | HIGH | MEDIUM | Graceful degradation, return empty checkpoint |
| **Malformed JSON** | MEDIUM | LOW | Robust JSON parsing with error handling |
| **Latency increase** | MEDIUM | LOW | Use fast model, async extraction, cache results |
| **Storage bloat** | LOW | LOW | Automatic cleanup, max 10 checkpoints |
| **Context leakage** | HIGH | LOW | Thread-scoped storage, validate thread_id |
| **False positives** (extracting too early) | LOW | MEDIUM | Minimum delta threshold (1000 tokens) |

---

## Part 8: Future Enhancements

### Short-term (After MVP)

1. **Checkpoint Versioning**
   - Version checkpoints to track evolution
   - Enable rollback to previous state

2. **Selective Injection**
   - Only inject relevant checkpoint fields
   - Use embeddings to match checkpoint to current query

3. **Compression**
   - Compress old checkpoints
   - Use delta encoding for similar checkpoints

### Long-term

1. **Predictive Checkpointing**
   - ML model to predict when to checkpoint
   - Learn from user feedback patterns

2. **Cross-Thread Checkpoints**
   - Share checkpoints across related threads
   - Global context for user patterns

3. **Hybrid Approach**
   - Combine prompt-based + middleware-based
   - Use prompt for coarse, middleware for fine-grained

---

## Part 9: Open Questions

1. **Checkpoint Granularity**: How detailed should checkpoints be?
   - **Recommendation**: Start coarse, refine based on user feedback

2. **Retention Policy**: How long to keep checkpoints?
   - **Recommendation**: Keep for thread lifetime, delete on thread close

3. **Extraction Model**: Which LLM to use for extraction?
   - **Recommendation**: Use fast model (gpt-5-mini or similar) for cost/latency

4. **Checkpoint Validation**: How to verify checkpoint quality?
   - **Recommendation**: User feedback mechanism ("Did I remember correctly?")

5. **Multi-Thread Support**: Should checkpoints be shared across threads?
   - **Recommendation**: No, keep thread-scoped for now (privacy/isolation)

---

## Conclusion

Strategic compaction is a low-risk, high-value feature that significantly improves user experience by preventing context loss during summarization.

**Recommended Implementation Order**:
1. **Start with prompt-based** (1-2 days) - Quick validation
2. **Add custom middleware** (3-5 days) - Robust solution
3. **Implement recovery** (2-3 days) - Make it useful
4. **Polish and test** (3-4 days) - Production-ready

**Total Timeline**: 2 weeks for complete implementation

**Next Steps**:
1. Review and approve this plan
2. Create feature branch: `feature/strategic-compaction`
3. Start with Phase 1 (prompt-based approach)
4. Iterate based on testing results

---

**Last Updated**: 2026-01-31
**Author**: Executive Assistant Team
**Status**: 📋 Planning
