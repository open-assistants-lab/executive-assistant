# Instincts System Roadmap

**Date:** 2025-02-02
**Status:** Active Development
**Related:** [personalization_refined.md](./personalization_refined.md), [onboarding_plan.md](./onboarding_plan.md)

---

## Overview

The **Instincts System** enables Executive Assistant to learn behavioral patterns organically from user interactions. This roadmap outlines the evolution from current capabilities to a sophisticated adaptive learning system.

### Current State (February 2025)

**What Works:**
- ✅ 4 pattern detections (corrections, repetitions, verbosity, format)
- ✅ Confidence scoring (0.0-1.0)
- ✅ 6 domains (communication, format, workflow, tool_selection, verification, timing)
- ✅ Append-only storage (JSONL + snapshot)
- ✅ System prompt injection per domain

**Known Gaps:**
- ⚠️ No conflict resolution for contradictory instincts
- ⚠️ No temporal decay (old instincts never fade)
- ⚠️ Underutilized metadata (occurrence_count, success_rate, last_triggered)
- ⚠️ Limited sources (missing 8 new detection types)
- ⚠️ Missing domains (emotional_state, learning_style)

---

## Roadmap Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ Phase 1: Quick Wins                 │ 1 day  │ Unblock new detections │
├─────────────────────────────────────────────────────────────────┤
│ Phase 2: Important Enhancements      │ 3 days │ Improve learning quality  │
├─────────────────────────────────────────────────────────────────┤
│ Phase 3: Architecture Expansion      │ 4 days │ Better organization        │
├─────────────────────────────────────────────────────────────────┤
│ Phase 4: Advanced Intelligence       │ 5 days │ Sophisticated adaptation    │
└─────────────────────────────────────────────────────────────────┘

Total: ~13 days of development work
```

---

## Phase 1: Quick Wins (1 day)

**Goal**: Unblock new detections immediately

### 1.1 Add Missing Sources ⚡ (30 minutes)

**File**: `src/executive_assistant/storage/instinct_storage.py`

**Current**:
```python
_ALLOWED_SOURCES = {
    "session-observation",
    "explicit-user",
    "repetition-confirmed",
    "correction-detected",
    "preference-expressed",
    "profile-preset",
    "custom-profile",
    "import",
}
```

**Add**:
```python
_ALLOWED_SOURCES = {
    # ... existing ...

    # Emotional state detection
    "frustration-detected",      # User shows frustration
    "confusion-detected",        # User seems confused
    "satisfaction-detected",     # User expresses satisfaction

    # Expertise tracking
    "expertise-detected",        # User declares expertise
    "domain-detected",           # Work domain identified

    # Contextual patterns
    "urgency-detected",          # Time pressure detected
    "learning-detected",         # User wants to learn
    "exploration-detected",      # User is experimenting
}
```

**Impact**: Unblocks all 7 new detections immediately

---

### 1.2 Basic Conflict Resolution ⚡ (2 hours)

**File**: `src/executive_assistant/instincts/injector.py`

**Problem**: Contradictory instincts confuse the LLM
```
Instinct A: "Be brief and concise" (confidence: 0.8)
Instinct B: "Provide thorough explanations" (confidence: 0.7)
→ Both injected → Confusion
```

**Solution**: Add priority system

```python
# Add to InstinctInjector class
CONFLICT_RESOLUTION = {
    # High-priority overrides
    ("timing", "urgent"): {
        "overrides": [
            ("communication", "detailed"),
            ("communication", "thorough"),
            ("learning", "explain"),
        ],
        "min_confidence": 0.6,
    },
    ("communication", "concise"): {
        "overrides": [
            ("communication", "detailed"),
            ("communication", "elaborate"),
        ],
        "min_confidence": 0.6,
    },
    ("emotional_state", "frustrated"): {
        "overrides": [
            ("workflow", "standard"),
            ("communication", "brief"),
        ],
        "min_confidence": 0.5,  # Lower threshold for emotional state
    },
}

def _resolve_conflicts(self, instincts: list[dict]) -> list[dict]:
    """Remove overridden instincts based on priority rules."""
    kept = []

    for instinct in instincts:
        domain = instinct["domain"]
        action = instinct["action"]
        confidence = instinct["confidence"]

        # Check if this instinct overrides others
        should_keep = True
        for kept_instinct in kept:
            key = (domain, action)

            # Check if kept_instinct overrides this one
            for override_key, rule in self.CONFLICT_RESOLUTION.items():
                override_domain, override_action = override_key

                if (kept_instinct["domain"] == override_domain and
                    override_action in kept_instinct["action"].lower() and
                    kept_instinct["confidence"] >= rule["min_confidence"]):

                    # Check if current instinct is in override list
                    for override_target in rule["overrides"]:
                        target_domain, target_action = override_target
                        if (domain == target_domain and
                            target_action in action.lower()):
                            should_keep = False
                            break

                if not should_keep:
                    break

        if should_keep:
            kept.append(instinct)

    return kept
```

**Update `build_instincts_context`**:
```python
def build_instincts_context(self, thread_id: str, ...):
    # ... existing loading logic ...

    # NEW: Resolve conflicts before formatting
    instincts = self._resolve_conflicts(instincts)

    # ... existing formatting logic ...
```

**Impact**: Prevents contradictory instructions to LLM

---

### 1.3 Use Occurrence Count for Confidence Boost ⚡ (30 minutes)

**File**: `src/executive_assistant/instincts/injector.py`

**Problem**: Reinforced instincts don't get stronger

**Solution**: Boost confidence for frequently-triggered instincts

```python
def build_instincts_context(self, thread_id: str, ...):
    # ... load instincts ...

    # NEW: Apply metadata-based confidence adjustment
    for instinct in instincts:
        metadata = instinct.get("metadata", {})
        occurrence_count = metadata.get("occurrence_count", 0)

        # Boost confidence for frequently reinforced instincts
        if occurrence_count >= 5:
            # Cap boost at +0.15
            boost = min(0.15, occurrence_count * 0.03)
            instinct["confidence"] = min(1.0, instinct["confidence"] + boost)
            instinct["confidence_boosted"] = True  # Track for debugging

    # ... rest of logic ...
```

**Impact**: Frequently-reinforced patterns get stronger

---

### 1.4 Testing & Validation (1 hour)

**Test Cases**:
```python
# test_conflict_resolution.py
def test_concise_overrides_detailed():
    """Concise instinct should override detailed when confident."""
    instincts = [
        {"domain": "communication", "action": "be brief and concise", "confidence": 0.8},
        {"domain": "communication", "action": "provide detailed explanations", "confidence": 0.7},
    ]
    resolved = injector._resolve_conflicts(instincts)
    assert len(resolved) == 1
    assert "concise" in resolved[0]["action"]

def test_urgency_overrides_explanation():
    """Urgency should override detailed explanations."""
    instincts = [
        {"domain": "timing", "action": "respond quickly", "confidence": 0.7},
        {"domain": "communication", "action": "provide thorough explanations", "confidence": 0.8},
        {"domain": "learning", "action": "explain reasoning", "confidence": 0.7},
    ]
    resolved = injector._resolve_conflicts(instincts)
    # Urgency and concise should remain, detailed explanations removed
    assert any(i["domain"] == "timing" for i in resolved)
    assert not any("thorough" in i["action"] for i in resolved)
```

**Manual Testing**:
1. Create conflicting instincts via conversation
2. Verify system prompt contains only highest-priority
3. Check logs for conflict resolution warnings

---

## Phase 2: Important Enhancements (3 days)

**Goal**: Make learning system adaptive and time-aware

### 2.1 Temporal Decay System (4 hours)

**File**: `src/executive_assistant/storage/instinct_storage.py`

**Problem**: Old instincts never fade, even if user preferences change

**Solution**: Implement confidence decay based on age and reinforcement

```python
# Add to InstinctStorage class
DECAY_CONFIG = {
    "half_life_days": 30,        # Confidence halves every 30 days without reinforcement
    "min_confidence": 0.3,       # Never decay below this
    "reinforcement_reset": True, # Reinforcement resets decay timer
}

def adjust_confidence_for_decay(self, instinct_id: str, thread_id: str | None = None) -> float:
    """Adjust instinct confidence based on age and lack of reinforcement."""
    instinct = self.get_instinct(instinct_id, thread_id)

    if not instinct:
        raise ValueError(f"Instinct {instinct_id} not found")

    created_at = datetime.fromisoformat(instinct["created_at"])
    days_old = (datetime.now(timezone.utc) - created_at).days

    metadata = instinct.get("metadata", {})
    occurrence_count = metadata.get("occurrence_count", 0)
    last_triggered = metadata.get("last_triggered")

    # Don't decay heavily reinforced instincts
    if occurrence_count >= 5:
        return instinct["confidence"]

    # Calculate decay
    half_life = self.DECAY_CONFIG["half_life_days"]
    min_conf = self.DECAY_CONFIG["min_confidence"]

    # Exponential decay: confidence * (0.5 ^ (days_old / half_life))
    decay_factor = 0.5 ** (days_old / half_life)
    new_confidence = max(min_conf, instinct["confidence"] * decay_factor)

    # Update if significantly changed
    if abs(new_confidence - instinct["confidence"]) > 0.05:
        self._set_confidence(instinct_id, new_confidence, thread_id)
        instinct["confidence"] = new_confidence

    return new_confidence

# Update list_instincts to apply decay
def list_instincts(self, thread_id: str | None = None, min_confidence: float = 0.0, ...):
    """List all instincts, applying temporal decay."""
    instincts = []  # ... existing loading logic ...

    # NEW: Apply decay before filtering
    for instinct in instincts:
        adjusted_confidence = self.adjust_confidence_for_decay(instinct["id"], thread_id)
        instinct["confidence"] = adjusted_confidence

    # Filter by min_confidence after decay
    return [i for i in instincts if i["confidence"] >= min_confidence]
```

**Storage Update** (track reinforcement history):
```python
def reinforce_instinct(self, instinct_id: str, thread_id: str | None = None) -> None:
    """Record that an instinct was triggered and relevant."""
    instinct = self.get_instinct(instinct_id, thread_id)
    if not instinct:
        return

    now = _utc_now()

    # Update metadata
    instinct["metadata"]["occurrence_count"] += 1
    instinct["metadata"]["last_triggered"] = now
    instinct["updated_at"] = now

    # Reset decay by bumping confidence slightly
    instinct["confidence"] = min(1.0, instinct["confidence"] + 0.05)

    # Save to storage
    self._update_instinct(instinct, thread_id)
```

**Impact**: System adapts to changing user preferences

---

### 2.2 Metadata Utilization (2 hours)

**File**: `src/executive_assistant/instincts/injector.py`

**Problem**: We track rich metadata but don't use it

**Solution**: Use all metadata fields for smarter injection

```python
def build_instincts_context(self, thread_id: str, user_message: str | None = None, ...):
    # ... load instincts ...

    # NEW: Comprehensive metadata-based filtering
    scored_instincts = []
    now = datetime.now(timezone.utc)

    for instinct in instincts:
        base_confidence = instinct["confidence"]
        metadata = instinct.get("metadata", {})

        # Factor 1: Occurrence count (frequency)
        occurrence_count = metadata.get("occurrence_count", 0)
        frequency_boost = min(0.15, occurrence_count * 0.03)

        # Factor 2: Recency (staleness penalty)
        last_triggered_str = metadata.get("last_triggered")
        if last_triggered_str:
            last_triggered = datetime.fromisoformat(last_triggered_str)
            days_since_trigger = (now - last_triggered).days
            staleness_penalty = max(-0.2, -days_since_trigger * 0.01)
        else:
            staleness_penalty = -0.1  # Never triggered

        # Factor 3: Success rate
        success_rate = metadata.get("success_rate", 1.0)
        success_multiplier = max(0.8, success_rate)

        # Combine factors
        final_confidence = base_confidence + frequency_boost + staleness_penalty
        final_confidence *= success_multiplier
        final_confidence = max(0.0, min(1.0, final_confidence))

        scored_instincts.append({
            **instinct,
            "final_confidence": final_confidence,
            "confidence_breakdown": {
                "base": base_confidence,
                "frequency_boost": frequency_boost,
                "staleness_penalty": staleness_penalty,
                "success_multiplier": success_multiplier,
            }
        })

    # Filter by final confidence
    instincts = [i for i in scored_instincts if i["final_confidence"] >= min_confidence]

    # Sort by final confidence
    instincts.sort(key=lambda i: i["final_confidence"], reverse=True)

    # ... rest of formatting logic ...
```

**Impact**: High-quality instincts float to top

---

### 2.3 Staleness Detection (2 hours)

**File**: `src/executive_assistant/storage/instinct_storage.py`

**Problem**: No way to identify outdated instincts

**Solution**: Add staleness detection and cleanup

```python
def get_stale_instincts(
    self,
    thread_id: str | None = None,
    days_since_trigger: int = 30,
    min_confidence: float = 0.5,
) -> list[dict]:
    """Get instincts that haven't been triggered recently.

    Useful for:
    - Identifying outdated patterns
    - Suggesting instinct cleanup
    - Debugging why certain behaviors changed
    """
    instincts = self.list_instincts(thread_id=thread_id, min_confidence=min_confidence)
    now = datetime.now(timezone.utc)
    stale = []

    for instinct in instincts:
        metadata = instinct.get("metadata", {})
        last_triggered_str = metadata.get("last_triggered")

        if not last_triggered_str:
            # Never triggered = definitely stale
            stale.append(instinct)
            continue

        last_triggered = datetime.fromisoformat(last_triggered_str)
        days = (now - last_triggered).days

        if days >= days_since_trigger:
            instinct["days_since_trigger"] = days
            stale.append(instinct)

    return stale

def cleanup_stale_instincts(
    self,
    thread_id: str | None = None,
    days_since_trigger: int = 60,
    min_confidence: float = 0.4,
) -> int:
    """Remove instincts that are old and rarely triggered.

    Returns count of removed instincts.
    """
    stale = self.get_stale_instincts(
        thread_id=thread_id,
        days_since_trigger=days_since_trigger,
        min_confidence=min_confidence,
    )

    removed_count = 0
    for instinct in stale:
        metadata = instinct.get("metadata", {})
        occurrence_count = metadata.get("occurrence_count", 0)

        # Only remove if rarely triggered
        if occurrence_count < 3:
            self.delete_instinct(instinct["id"], thread_id)
            removed_count += 1

    return removed_count
```

**Admin Command** (for debugging):
```bash
exec_assistant instincts --stale
exec_assistant instincts --cleanup
```

**Impact**: Keeps instinct database healthy

---

### 2.4 Success Rate Tracking (4 hours)

**File**: `src/executive_assistant/instincts/observer.py`

**Problem**: No way to know if instincts actually help

**Solution**: Track implicit success signals

```python
# Add to InstinctObserver
SATISFACTION_PATTERNS = {
    "triggers": [
        r"\b(perfect|great|awesome|thanks|exactly what)\b",
        r"\b(that's what I needed|just what I wanted)\b",
        r"\b(love it|amazing|brilliant)\b",
        r"👍|✅|🎉",
    ],
}

FRUSTRATION_PATTERNS = {
    "triggers": [
        r"\b(nevermind|forget it|whatever)\b",
        r"^(ok|okay|fine)[!.]*$",
        r"\?+$",
    ],
}

def record_outcome(
    self,
    instinct_id: str,
    success: bool,
    thread_id: str | None = None,
) -> None:
    """Record whether applying an instinct led to success.

    Success = positive user signals (satisfaction, continued conversation)
    Failure = negative signals (frustration, correction)
    """
    from executive_assistant.storage.instinct_storage import get_instinct_storage
    storage = get_instinct_storage()

    instinct = storage.get_instinct(instinct_id, thread_id)
    if not instinct:
        return

    metadata = instinct.get("metadata", {})

    # Update success rate (moving average)
    current_rate = metadata.get("success_rate", 1.0)
    alpha = 0.2  # Learning rate
    new_rate = (alpha * (1.0 if success else 0.0)) + ((1 - alpha) * current_rate)

    metadata["success_rate"] = new_rate

    # Save
    storage.update_instinct_metadata(instinct_id, metadata, thread_id)


def observe_conversation_outcome(
    self,
    user_message: str,
    applied_instinct_ids: list[str],
    thread_id: str | None = None,
) -> None:
    """Detect if instincts led to positive or negative outcome."""
    # Check for satisfaction
    for pattern in self.SATISFACTION_PATTERNS["triggers"]:
        if re.search(pattern, user_message, re.IGNORECASE):
            # Record success for all applied instincts
            for instinct_id in applied_instinct_ids:
                self.record_outcome(instinct_id, success=True, thread_id=thread_id)
            return

    # Check for frustration
    for pattern in self.FRUSTRATION_PATTERNS["triggers"]:
        if re.search(pattern, user_message, re.IGNORECASE):
            # Record failure for all applied instincts
            for instinct_id in applied_instinct_ids:
                self.record_outcome(instinct_id, success=False, thread_id=thread_id)
            return
```

**Integration** (in channels/base.py):
```python
# After agent generates response
applied_instincts = load_instincts_context(thread_id, user_message)

# ... agent responds ...

# Next message from user
observer.observe_conversation_outcome(
    user_message,
    applied_instincts,
    thread_id,
)
```

**Impact**: System learns which instincts actually help

---

## Phase 3: Architecture Expansion (4 days)

**Goal**: Better organization for new detection types

### 3.1 Add New Domains (2 hours)

**File**: `src/executive_assistant/storage/instinct_storage.py`

**Current**:
```python
_ALLOWED_DOMAINS = {
    "communication",
    "format",
    "workflow",
    "tool_selection",
    "verification",
    "timing",
}
```

**Add**:
```python
_ALLOWED_DOMAINS = {
    # ... existing ...

    # NEW: User's emotional/mental state
    "emotional_state",        # Frustrated, confused, satisfied

    # NEW: How user prefers to learn
    "learning_style",         # Teaching mode, exploration, hands-on

    # NEW: Domain expertise tracking
    "expertise",              # Technical areas user knows/doesn't know
}
```

**Update Injector Templates**:
```python
# File: src/executive_assistant/instincts/injector.py

DOMAIN_TEMPLATES = {
    # ... existing ...

    "emotional_state": """## Emotional Context
The user appears to be in the following emotional state:
{actions}

Adjust your response accordingly:
- Be extra supportive and patient
- Offer to break down complex tasks
- Provide alternative approaches
""",

    "learning_style": """## Learning Approach
Based on past interactions, the user prefers:
{actions}

Adapt your explanations:
- Teaching mode: Show reasoning, offer resources
- Exploration mode: Provide options, explain trade-offs
- Hands-on mode: Focus on practical implementation
""",

    "expertise": """## Known Expertise Areas
The user has demonstrated knowledge in:
{actions}

Adjust your explanations:
- Skip basics in known areas
- Provide context for new topics
- Assume familiarity with domain terminology
""",
}
```

**Impact**: Cleaner categorization of new detection types

---

### 3.2 Context-Aware Instinct Filtering (4 hours)

**File**: `src/executive_assistant/instincts/injector.py`

**Problem**: All instincts apply equally, regardless of context

**Example**:
- User has urgency instinct: "respond quickly"
- User is now asking a complex research question
- System should NOT apply urgency (conflict!)

**Solution**: Contextual filtering

```python
def build_instincts_context(
    self,
    thread_id: str,
    user_message: str | None = None,
    conversation_history: list[dict] | None = None,  # NEW
    min_confidence: float = 0.5,
    max_per_domain: int = 3,
) -> str:
    """Build instincts section with context-aware filtering."""

    # ... load instincts ...

    # NEW: Context-aware filtering
    if user_message:
        instincts = self._filter_by_context(
            instincts,
            user_message,
            conversation_history,
        )

    # ... rest of logic ...

def _filter_by_context(
    self,
    instincts: list[dict],
    user_message: str,
    conversation_history: list[dict] | None = None,
) -> list[dict]:
    """Filter instincts based on current context."""

    # 1. Detect conversation type
    is_quick_question = len(user_message) < 100
    is_complex_task = any(word in user_message.lower() for word in
                         ["analyze", "research", "investigate", "explore"])
    is_followup = conversation_history and len(conversation_history) > 3

    # 2. Filter based on context
    filtered = []
    for instinct in instincts:
        domain = instinct["domain"]
        action = instinct["action"].lower()

        # Urgency: Don't apply to complex tasks
        if domain == "timing" and "quick" in action:
            if is_complex_task:
                continue  # Skip urgency instinct

        # Learning mode: Don't apply to quick questions
        if domain == "learning_style" and "explain" in action:
            if is_quick_question:
                continue

        # Conciseness: Less strict in follow-up conversations
        if domain == "communication" and "brief" in action:
            if is_followup:
                # Reduce confidence for conciseness in follow-ups
                instinct["confidence"] *= 0.7

        filtered.append(instinct)

    return filtered
```

**Impact**: Right instinct for right situation

---

### 3.3 Instinct Clustering (4 hours)

**File**: `src/executive_assistant/storage/instinct_storage.py`

**Problem**: Too many related instincts clutter the system

**Example**:
```
Instinct A: "User prefers concise responses" (communication)
Instinct B: "User likes brief answers" (communication)
Instinct C: "User wants short replies" (communication)
→ These are all the same thing!
```

**Solution**: Auto-merge similar instincts

```python
def find_similar_instincts(
    self,
    thread_id: str | None = None,
    similarity_threshold: float = 0.8,
) -> list[list[dict]]:
    """Find instincts that are semantically similar.

    Returns clusters of similar instincts.
    """
    instincts = self.list_instincts(thread_id=thread_id)

    # Simple similarity: trigger/action text similarity
    clusters = []
    used = set()

    for i, instinct_a in enumerate(instincts):
        if i in used:
            continue

        cluster = [instinct_a]
        used.add(i)

        for j, instinct_b in enumerate(instincts[i+1:], start=i+1):
            if j in used:
                continue

            # Calculate similarity
            sim = self._calculate_similarity(instinct_a, instinct_b)

            if sim >= similarity_threshold:
                cluster.append(instinct_b)
                used.add(j)

        if len(cluster) > 1:
            clusters.append(cluster)

    return clusters

def _calculate_similarity(self, instinct_a: dict, instinct_b: dict) -> float:
    """Calculate semantic similarity between two instincts."""
    # Simple word-overlap similarity (can upgrade to embeddings)
    text_a = f"{instinct_a['trigger']} {instinct_a['action']}"
    text_b = f"{instinct_b['trigger']} {instinct_b['action']}"

    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())

    if not words_a or not words_b:
        return 0.0

    intersection = words_a & words_b
    union = words_a | words_b

    return len(intersection) / len(union)

def merge_similar_instincts(
    self,
    thread_id: str | None = None,
) -> int:
    """Merge similar instincts, keeping highest-confidence version."""
    clusters = self.find_similar_instincts(thread_id=thread_id)

    merged_count = 0
    for cluster in clusters:
        # Keep highest confidence
        cluster.sort(key=lambda i: i["confidence"], reverse=True)
        keeper = cluster[0]

        # Merge confidence from others
        for instinct in cluster[1:]:
            # Boost keeper confidence
            new_confidence = min(1.0, keeper["confidence"] + (instinct["confidence"] * 0.3))
            self._set_confidence(keeper["id"], new_confidence, thread_id)

            # Merge metadata
            keeper_metadata = keeper.get("metadata", {})
            other_metadata = instinct.get("metadata", {})

            keeper_metadata["occurrence_count"] += other_metadata.get("occurrence_count", 0)

            # Delete duplicate
            self.delete_instinct(instinct["id"], thread_id)
            merged_count += 1

    return merged_count
```

**Admin Command**:
```bash
exec_assistant instincts --deduplicate
```

**Impact**: Cleaner instinct database

---

### 3.4 Emotional State Tracking System (6 hours)

**File**: `src/executive_assistant/instincts/emotional_tracker.py` (NEW)

**Problem**: Emotions are complex, not just "frustrated" or "satisfied"

**Solution**: Sophisticated emotional state tracking

```python
"""Emotional state tracking for user interactions.

Tracks emotional trajectory over conversation to provide context.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

class EmotionalState(Enum):
    """User's current emotional state."""
    NEUTRAL = "neutral"
    ENGAGED = "engaged"           # Active, interested
    CONFUSED = "confused"         # Needs clarification
    FRUSTRATED = "frustrated"     # Negative, needs support
    SATISFIED = "satisfied"       # Positive, successful
    OVERWHELMED = "overwhelmed"   # Too much info
    CURIOUS = "curious"           # Exploring
    URGENT = "urgent"             # Time pressure

class EmotionalTracker:
    """Track user's emotional state across conversation."""

    def __init__(self):
        # Current state and confidence
        self.current_state = EmotionalState.NEUTRAL
        self.confidence = 0.5

        # History (last 10 states)
        self.history = []  # List of (state, confidence, timestamp)

        # Transition patterns we've learned
        self.transitions = {}  # (from_state, to_state) -> count

    def update_state(
        self,
        user_message: str,
        assistant_message: str | None = None,
        conversation_length: int = 0,
    ) -> EmotionalState:
        """Update emotional state based on latest interaction."""

        # Detect emotional signals from user message
        detected_state = self._detect_emotional_state(user_message)

        # Consider context
        if conversation_length < 2:
            # Early conversation: more likely to be curious/confused
            if detected_state == EmotionalState.NEUTRAL:
                detected_state = EmotionalState.CURIOUS

        # Smooth transitions (don't jump abruptly)
        if self._is_abrupt_transition(self.current_state, detected_state):
            # Reduce confidence, keep current state
            self.confidence *= 0.7
        else:
            # Record transition
            key = (self.current_state, detected_state)
            self.transitions[key] = self.transitions.get(key, 0) + 1

            # Update state with smoothing
            alpha = 0.3  # Smoothing factor
            if self.current_state != detected_state:
                self.confidence = alpha + (self.confidence * (1 - alpha))
            else:
                self.confidence = min(1.0, self.confidence + 0.1)

            self.current_state = detected_state

        # Add to history
        self.history.append({
            "state": self.current_state,
            "confidence": self.confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Keep only last 10
        if len(self.history) > 10:
            self.history.pop(0)

        return self.current_state

    def _detect_emotional_state(self, message: str) -> EmotionalState:
        """Detect emotional state from user message."""

        patterns = {
            EmotionalState.FRUSTRATED: [
                r"\b(nevermind|forget it|whatever)\b",
                r"^(ok|okay|fine)[!.]*$",
                r"\?+$",
            ],
            EmotionalState.SATISFIED: [
                r"\b(perfect|great|awesome|thanks|exactly)\b",
                r"👍|✅|🎉",
            ],
            EmotionalState.CONFUSED: [
                r"\b(don't understand|confused|doesn't make sense)\b",
                r"\b(what do you mean|explain again)\b",
            ],
            EmotionalState.OVERWHELMED: [
                r"\b(too much|overwhelming|information overload)\b",
                r"\b(step back|simplify)\b",
            ],
            EmotionalState.URGENT: [
                r"\b(asap|urgent|emergency|immediately)\b",
                r"\b(hurry|quick|deadline)\b",
            ],
            EmotionalState.CURIOUS: [
                r"\b(just curious|wondering|can you)\b",
                r"\b(what if|try|experiment)\b",
            ],
        }

        message_lower = message.lower()

        # Check each state's patterns
        for state, state_patterns in patterns.items():
            for pattern in state_patterns:
                if re.search(pattern, message_lower):
                    return state

        return EmotionalState.NEUTRAL

    def _is_abrupt_transition(
        self,
        from_state: EmotionalState,
        to_state: EmotionalState,
    ) -> bool:
        """Check if transition is too abrupt."""

        # Allowed transitions
        allowed = {
            EmotionalState.NEUTRAL: {
                EmotionalState.ENGAGED,
                EmotionalState.CURIOUS,
                EmotionalState.CONFUSED,
                EmotionalState.FRUSTRATED,
            },
            EmotionalState.ENGAGED: {
                EmotionalState.SATISFIED,
                EmotionalState.CONFUSED,
                EmotionalState.FRUSTRATED,
            },
            EmotionalState.CONFUSED: {
                EmotionalState.ENGAGED,
                EmotionalState.OVERWHELMED,
                EmotionalState.FRUSTRATED,
            },
            EmotionalState.FRUSTRATED: {
                EmotionalState.SATISFIED,  # Recovery!
                EmotionalState.NEUTRAL,
            },
        }

        return to_state not in allowed.get(from_state, set())

    def get_state_for_prompt(self) -> str:
        """Get formatted state for system prompt injection."""

        if self.current_state == EmotionalState.NEUTRAL or self.confidence < 0.6:
            return ""  # Don't inject if uncertain

        guidance = {
            EmotionalState.FRUSTRATED: (
                "The user appears frustrated. "
                "Be extra supportive, offer alternatives, "
                "and break down complex tasks."
            ),
            EmotionalState.CONFUSED: (
                "The user seems confused. "
                "Simplify your explanations, use concrete examples, "
                "and check for understanding."
            ),
            EmotionalState.OVERWHELMED: (
                "The user is overwhelmed. "
                "Reduce information density, focus on one thing at a time, "
                "and offer to skip details."
            ),
            EmotionalState.URGENT: (
                "The user is in a hurry. "
                "Skip explanations, go straight to solutions, "
                "and prioritize speed over completeness."
            ),
            EmotionalState.SATISFIED: (
                "The user is satisfied with current approach. "
                "Continue with this style."
            ),
            EmotionalState.CURIOUS: (
                "The user is exploring. "
                "Offer options, explain trade-offs, "
                "and suggest alternative approaches."
            ),
            EmotionalState.ENGAGED: (
                "The user is actively engaged. "
                "Match their energy level and dive into details."
            ),
        }

        return guidance.get(self.current_state, "")

# Singleton instance
_emotional_tracker = EmotionalTracker()

def get_emotional_tracker() -> EmotionalTracker:
    return _emotional_tracker
```

**Integration** (in channels/base.py):
```python
# Track emotional state
tracker = get_emotional_tracker()
state = tracker.update_state(message.content, conversation_history=len(history))

# Inject into system prompt if significant
if state != EmotionalState.NEUTRAL:
    emotional_context = tracker.get_state_for_prompt()
    # Add to system prompt
```

**Impact**: Empathetic, context-aware responses

---

### 3.5 Expertise Domain Mapping (4 hours)

**File**: `src/executive_assistant/instincts/expertise_mapper.py` (NEW)

**Problem**: User expertise is more complex than "knows Python"

**Solution**: Multi-dimensional expertise tracking

```python
"""Expertise mapping for user knowledge domains.

Tracks what user knows/doesn't know across different technical areas.
"""

from dataclasses import dataclass
from typing import Dict, List

@dataclass
class ExpertiseLevel:
    """User's expertise level in a domain."""
    domain: str
    level: float  # 0.0 (novice) to 1.0 (expert)
    confidence: float  # How certain we are
    last_confirmed: str  # ISO timestamp

class ExpertiseMapper:
    """Map and track user expertise across domains."""

    # Common technical domains
    DOMAINS = [
        "python", "javascript", "sql", "docker", "kubernetes",
        "machine_learning", "data_analysis", "web_development",
        "api_design", "database_design", "devops", "testing",
        "git", "linux", "networking", "security",
    ]

    def __init__(self):
        self.expertise: Dict[str, ExpertiseLevel] = {}

    def detect_expertise_claims(
        self,
        user_message: str,
    ) -> List[tuple[str, float]]:
        """Detect user claiming expertise or lack thereof.

        Returns list of (domain, level) tuples.
        """
        detected = []

        # Pattern: "I know Python" / "I'm new to Kubernetes"
        patterns = [
            (r"\bi know (python|javascript|sql|docker|kubernetes|ml|ai)\b", 0.8),
            (r"\bi'm (an expert at|good at|skilled in) (\w+)", 0.9),
            (r"\bi'm (new to|learning|not familiar with) (\w+)", 0.2),
            (r"\bi've never used (\w+)\b", 0.1),
            (r"\bi don't know (python|javascript|sql)\b", 0.1),
        ]

        message_lower = user_message.lower()

        for pattern, level in patterns:
            match = re.search(pattern, message_lower)
            if match:
                # Extract domain
                domain = match.group(1) if match.lastindex else match.group(2)
                detected.append((domain, level))

        return detected

    def update_expertise(
        self,
        domain: str,
        level: float,
        confidence: float = 0.7,
    ) -> None:
        """Update expertise level for a domain."""

        if domain in self.expertise:
            # Update with smoothing
            existing = self.expertise[domain]
            alpha = 0.3

            new_level = (alpha * level) + ((1 - alpha) * existing.level)
            new_confidence = min(1.0, existing.confidence + 0.1)

            self.expertise[domain] = ExpertiseLevel(
                domain=domain,
                level=new_level,
                confidence=new_confidence,
                last_confirmed=datetime.now(timezone.utc).isoformat(),
            )
        else:
            # Create new
            self.expertise[domain] = ExpertiseLevel(
                domain=domain,
                level=level,
                confidence=confidence,
                last_confirmed=datetime.now(timezone.utc).isoformat(),
            )

    def get_expertise_for_prompt(self) -> str:
        """Get formatted expertise for system prompt."""

        if not self.expertise:
            return ""

        # Group by level
        expert = []
        intermediate = []
        novice = []

        for domain, info in self.expertise.items():
            if info.level >= 0.7:
                expert.append(domain)
            elif info.level >= 0.4:
                intermediate.append(domain)
            else:
                novice.append(domain)

        sections = []

        if expert:
            sections.append(f"**Expert in**: {', '.join(expert)}")
            sections.append("- Skip basic explanations, use advanced terminology")

        if intermediate:
            sections.append(f"**Familiar with**: {', '.join(intermediate)}")
            sections.append("- Provide context, avoid oversimplifying")

        if novice:
            sections.append(f"**Learning**: {', '.join(novice)}")
            sections.append("- Explain fundamentals, provide examples")

        return "\n".join(sections)

# Singleton
_expertise_mapper = ExpertiseMapper()

def get_expertise_mapper() -> ExpertiseMapper:
    return _expertise_mapper
```

**Integration** (in observer.py):
```python
def observe_message(self, user_message: str, ...):
    # ... existing pattern detection ...

    # NEW: Detect expertise claims
    from executive_assistant.instincts.expertise_mapper import get_expertise_mapper

    mapper = get_expertise_mapper()
    for domain, level in mapper.detect_expertise_claims(user_message):
        mapper.update_expertise(domain, level)
```

**Impact**: Domain-aware explanations

---

## Phase 4: Advanced Intelligence (5 days)

**Goal**: Sophisticated learning and adaptation

### 4.1 Cross-Instinct Pattern Recognition (6 hours)

**Problem**: Patterns across domains are missed

**Example**:
- User prefers concise responses (communication)
- User wants to learn (learning_style)
- **Combined**: "Show code first, then explain briefly"

**Solution**: Detect and create composite instincts

```python
# File: src/executive_assistant/instincts/pattern_recognizer.py

class PatternRecognizer:
    """Recognize higher-level patterns from instinct combinations."""

    def __init__(self):
        # Learned composite patterns
        self.composites = []

    def analyze_conversation(
        self,
        active_instincts: list[dict],
        user_satisfaction: bool,
    ) -> None:
        """Analyze which instinct combinations lead to success."""

        # Create combination signature
        signature = self._create_signature(active_instincts)

        # Record outcome
        signature["success"] = user_satisfaction
        signature["timestamp"] = datetime.now(timezone.utc).isoformat()

        self.composites.append(signature)

        # Find successful patterns
        successful = [c for c in self.composites if c["success"]]

        # Cluster successful patterns
        clusters = self._cluster_patterns(successful)

        # Suggest new instincts
        for cluster in clusters:
            if len(cluster) >= 3:  # Pattern seen 3+ times
                self._suggest_composite_instinct(cluster)

    def _create_signature(self, instincts: list[dict]) -> dict:
        """Create signature from instinct combination."""
        return {
            "domains": sorted(set(i["domain"] for i in instincts)),
            "actions": sorted([i["action"][:50] for i in instincts]),  # First 50 chars
        }

    def _cluster_patterns(self, patterns: list[dict]) -> list[list[dict]]:
        """Cluster similar patterns."""
        # Simple clustering: group by identical domain/action sets
        clusters = {}

        for pattern in patterns:
            key = (
                tuple(pattern["domains"]),
                tuple(pattern["actions"]),
            )
            if key not in clusters:
                clusters[key] = []
            clusters[key].append(pattern)

        return list(clusters.values())

    def _suggest_composite_instinct(self, cluster: list[dict]) -> dict:
        """Suggest a new instinct from successful pattern."""

        # Extract common elements
        example = cluster[0]

        # Create composite action
        domains = example["domains"]
        actions = example["actions"]

        composite_action = f"Combined approach: {', '.join(actions[:3])}"

        return {
            "trigger": f"user context matches pattern: {', '.join(domains)}",
            "action": composite_action,
            "domain": "workflow",
            "source": "pattern-recognition",
            "confidence": min(1.0, len(cluster) * 0.2),
            "evidence_count": len(cluster),
        }
```

**Impact**: Learns complex multi-domain behaviors

---

### 4.2 Confidence Calibration System (6 hours)

**Problem**: Confidence scores don't reflect actual accuracy

**Solution**: Track prediction vs reality

```python
# File: src/executive_assistant/instincts/calibrator.py

class ConfidenceCalibrator:
    """Calibrate instinct confidence based on actual outcomes."""

    def __init__(self):
        # History of (predicted_confidence, actual_outcome)
        self.history = []

    def record_prediction(
        self,
        predicted_confidence: float,
        actual_outcome: bool,  # True = user was satisfied
        instinct_id: str,
    ) -> None:
        """Record whether confidence prediction was accurate."""

        self.history.append({
            "predicted": predicted_confidence,
            "actual": actual_outcome,
            "instinct_id": instinct_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Periodic calibration (every 50 predictions)
        if len(self.history) % 50 == 0:
            self._calibrate()

    def _calibrate(self) -> None:
        """Adjust confidence scoring based on history."""

        # Calculate calibration curve
        bins = {}
        for entry in self.history:
            pred = round(entry["predicted"], 1)
            if pred not in bins:
                bins[pred] = {"correct": 0, "total": 0}

            bins[pred]["total"] += 1
            if entry["actual"]:
                bins[pred]["correct"] += 1

        # Find systematic biases
        adjustments = {}
        for conf, stats in bins.items():
            if stats["total"] < 5:
                continue

            actual_rate = stats["correct"] / stats["total"]
            predicted_rate = conf

            # If we're overconfident, reduce; underconfident, increase
            if actual_rate < predicted_rate - 0.1:
                adjustments[conf] = -0.1  # Overconfident
            elif actual_rate > predicted_rate + 0.1:
                adjustments[conf] = 0.1  # Underconfident

        # Apply adjustments
        self._apply_adjustments(adjustments)

    def _apply_adjustments(self, adjustments: dict) -> None:
        """Apply calibration adjustments to storage."""
        from executive_assistant.storage.instinct_storage import get_instinct_storage

        storage = get_instinct_storage()

        # Get all instincts
        for thread_id in storage.get_all_threads():
            instincts = storage.list_instincts(thread_id=thread_id)

            for instinct in instincts:
                conf = round(instinct["confidence"], 1)
                if conf in adjustments:
                    new_conf = max(0.0, min(1.0,
                        instinct["confidence"] + adjustments[conf]
                    ))
                    storage._set_confidence(instinct["id"], new_conf, thread_id)
```

**Impact**: Confidence scores become meaningful

---

### 4.3 Adaptive Instinct Injection (4 hours)

**File**: `src/executive_assistant/instincts/injector.py`

**Problem**: Fixed max_per_domain doesn't adapt

**Solution**: Dynamic limit based on quality

```python
def build_instincts_context(
    self,
    thread_id: str,
    user_message: str | None = None,
    min_confidence: float = 0.5,
    max_per_domain: int = None,  # None = adaptive
) -> str:
    """Build instincts section with adaptive limits."""

    # ... load instincts ...

    if max_per_domain is None:
        # Adaptive: more instincts if they're high-quality
        avg_confidence = sum(i["confidence"] for i in instincts) / len(instincts)

        if avg_confidence > 0.8:
            max_per_domain = 5  # Many high-quality instincts
        elif avg_confidence > 0.6:
            max_per_domain = 3  # Standard
        else:
            max_per_domain = 1  # Only best instincts

    # ... rest of logic ...
```

**Impact**: Better instincts get more exposure

---

### 4.4 Instinct Explanation System (4 hours)

**Problem**: Users don't know what the system learned

**Solution**: Explainable instincts

```python
# File: src/executive_assistant/tools/instincts_viewer.py

@tool
def view_what_agent_learned() -> str:
    """Show what the agent has learned about you.

    Useful for:
    - Understanding why the agent behaves certain ways
    - Correcting misconceptions
    - Seeing learning progress
    """
    from executive_assistant.storage.instinct_storage import get_instinct_storage

    storage = get_instinct_storage()
    instincts = storage.list_instincts(min_confidence=0.6)

    if not instincts:
        return "I haven't learned much about you yet. The more we interact, the better I'll understand your preferences!"

    # Group by domain
    by_domain = {}
    for instinct in instincts:
        domain = instinct["domain"]
        if domain not in by_domain:
            by_domain[domain] = []
        by_domain[domain].append(instinct)

    # Format for user
    sections = []
    sections.append("# What I've Learned About You")
    sections.append("")

    for domain, domain_instincts in sorted(by_domain.items()):
        sections.append(f"## {domain.replace('_', ' ').title()}")

        for instinct in sorted(domain_instincts, key=lambda i: -i["confidence"]):
            confidence_percent = int(instinct["confidence"] * 100)
            sections.append(f"- **{instinct['action']}** ({confidence_percent}% confidence)")

        sections.append("")

    sections.append("I learn these patterns from our conversations. If something seems wrong, just let me know!")

    return "\n".join(sections)
```

**Impact**: Transparency builds trust

---

### 4.5 Instinct Export/Import (2 hours)

**Problem**: Learned patterns can't be shared or backed up

**Solution**: Import/export instincts

```python
# File: src/executive_assistant/tools/instincts_io.py

@tool
def export_instincts() -> str:
    """Export learned instincts as JSON.

    Useful for:
    - Backing up learned preferences
    - Sharing between installations
    - Manual inspection
    """
    from executive_assistant.storage.instinct_storage import get_instinct_storage

    storage = get_instinct_storage()
    instincts = storage.list_instincts()

    export_data = {
        "version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "instincts": instincts,
    }

    return json.dumps(export_data, indent=2)

@tool
def import_instincts(json_data: str) -> str:
    """Import instincts from JSON export.

    Args:
        json_data: JSON string from export_instincts()

    Useful for:
    - Restoring from backup
    - Migrating to new installation
    """
    from executive_assistant.storage.instinct_storage import get_instinct_storage

    storage = get_instinct_storage()

    try:
        data = json.loads(json_data)

        imported = 0
        for instinct_data in data["instincts"]:
            storage.create_instinct(
                trigger=instinct_data["trigger"],
                action=instinct_data["action"],
                domain=instinct_data["domain"],
                source="import",
                confidence=instinct_data["confidence"],
            )
            imported += 1

        return f"Imported {imported} instincts successfully."

    except Exception as e:
        return f"Import failed: {str(e)}"
```

**Impact**: Portability and backup

---

## Success Metrics

### Quantitative

- **Instinct Quality**: Average confidence should increase from 0.6 → 0.8
- **Conflict Rate**: Contradictory instincts should decrease by 80%
- **Staleness**: < 10% of instincts should be stale (>30 days old)
- **Success Rate**: Tracked instincts should have > 70% success rate
- **User Satisfaction**: Measured via satisfaction detection

### Qualitative

- Responses feel more "in tune" with user
- Fewer corrections needed over time
- System adapts to preference changes
- No contradictory instructions to LLM
- Emotional state handled empathetically

---

## Testing Strategy

### Unit Tests

```python
# tests/test_instincts_conflict.py
def test_urgency_overrides_detailed()
def test_confidence_decay()
def test_staleness_detection()

# tests/test_instincts_clustering.py
def test_similar_instinct_detection()
def test_instinct_merging()

# tests/test_emotional_tracking.py
def test_emotional_state_detection()
def test_abrupt_transition_blocking()
```

### Integration Tests

```python
# tests/test_instincts_workflow.py
def test_full_learning_workflow():
    """Test: User says "be brief" → instinct created → applied in next response"""
    pass

def test_preference_change():
    """Test: User changes preference → old instinct decays → new one takes over"""
    pass
```

### Manual Testing Scenarios

1. **Preference Evolution**:
   - Day 1: User prefers concise
   - Day 15: User switches to detailed
   - Day 30: Verify concise instinct decayed

2. **Conflict Resolution**:
   - Create urgency + learning instincts
   - Verify urgency wins

3. **Emotional Trajectory**:
   - Start neutral
   - Become confused
   - Become frustrated
   - Recover to satisfied
   - Verify smooth transitions

---

## Open Questions

1. **Should instincts be shareable across threads?**
   - Pro: Learn faster
   - Con: Privacy concerns

2. **How to handle conflicting emotional signals?**
   - User says "great" but also "confused"
   - Weight by confidence?

3. **Should we use embeddings for similarity detection?**
   - More accurate but slower
   - Current word-overlap is fast but crude

4. **How often to run maintenance tasks?**
   - Decay calculation
   - Clustering
   - Cleanup

---

## Next Steps

1. **Review and prioritize** phases with team
2. **Set up testing environment** for instincts
3. **Start with Phase 1** (Quick Wins)
4. **Gather user feedback** after each phase
5. **Iterate** based on real-world usage

---

## Conclusion

This roadmap transforms the instincts system from a simple pattern detector into a sophisticated adaptive learning engine. The phased approach allows for incremental value delivery while building toward a comprehensive solution.

**Key Philosophy**: Learn organically, adapt continuously, explain clearly.

The system should feel like a human assistant: observant, adaptive, empathetic, and always improving. 🎯
