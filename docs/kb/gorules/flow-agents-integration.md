# GoRules for Flow & Mini-Agent System

## Executive Summary

**Question**: Could GoRules be used with flows and mini-agents?

**Answer**: ✅ **YES** - But only for specific use cases. GoRules excels at **policy enforcement** around agents/flows, not natural language understanding.

**Key insight**: Use LLM to understand user intent, GoRules to enforce business rules (quotas, validation, security).

---

## Current System Architecture

### Mini-Agents
```python
create_agent(
    agent_id="researcher",
    name="Research Assistant",
    description="Searches and summarizes web content",
    tools=["search_tool", "firecrawl_tool"],
    system_prompt="You are a research assistant...",
    output_schema={"summary": "str", "sources": "list"}
)
```

**Capabilities**:
- Per-user agent registry
- Custom tools, prompts, output schemas
- Tool composition (max 10 tools recommended ≤5)

### Flows
```python
create_flow(
    name="Daily Research Briefing",
    agent_ids=["researcher", "writer"],
    schedule_type="recurring",
    cron_expression="0 9 * * *",  # Daily at 9am
    middleware={
        "model_call_limit": 5,
        "tool_call_limit": 10
    }
)
```

**Capabilities**:
- Chain multiple agents in sequence
- Immediate, scheduled, or recurring execution
- Middleware limits (model calls, tool calls, retries)
- Notification on complete/failure

### Current Validation (Hand-coded)
```python
# In flow_tools.py lines 86-158
- Check agents exist
- Validate tool limits (>5 warning, >10 error)
- First agent must use $input when flow_input provided
- Forbid flow tools within flows (prevent recursion)
- Validate middleware limits (<=10)
- Cron validation ("* * * * *" not allowed)
```

---

## ✅ Strong Fit: Agent Creation Policy

### Problem
Current validation is scattered and hard-coded:
```python
# Lines 108-111 in flow_tools.py
if agent and len(agent.tools) > 5:
    warnings.append(f"{agent_id} uses {len(agent.tools)} tools")
```

**Limitations**:
- Hard-coded in Python
- Can't easily adjust per user tier
- No audit trail
- Hard to add new rules

### GoRules Solution

**Decision Graph**:
```json
{
  "name": "agent-creation-policy",
  "rules": [
    {
      "rule_id": "tool_limit_free_tier",
      "conditions": {
        "user_tier": "free",
        "tool_count": ">3"
      },
      "action": "reject",
      "message": "Free tier limited to 3 tools per agent"
    },
    {
      "rule_id": "tool_limit_premium_tier",
      "conditions": {
        "user_tier": "premium",
        "tool_count": ">10"
      },
      "action": "reject",
      "message": "Premium tier limited to 10 tools per agent"
    },
    {
      "rule_id": "dangerous_tools",
      "conditions": {
        "tools": "includes_any",
        "list": ["delete_files", "execute_python", "bash_command"]
      },
      "conditions": {
        "user_tier": "free"
      },
      "action": "reject",
      "message": "Dangerous tools require premium tier"
    },
    {
      "rule_id": "output_schema_required",
      "conditions": {
        "agent_type": "flow_agent",
        "has_output_schema": false
      },
      "action": "reject",
      "message": "Flow agents must have output_schema for agent chaining"
    }
  ]
}
```

**Benefits**:
- ✅ Per-user-tier policies (free vs premium)
- ✅ Explainable rejections ("Tool limit exceeded: 4/3 for free tier")
- ✅ Easy to update (no code changes)
- ✅ Audit trail (who was rejected and why)
- ✅ Consistent enforcement

**Implementation Priority**: ⭐⭐⭐ **HIGH** (Scalability requirement)

---

## ✅ Strong Fit: Flow Validation Rules

### Problem
Current flow validation is complex and scattered (lines 86-158):
```python
# Multiple if statements
if missing: return error
if len(tools) > 5: warnings.append(...)
if "$input" not in prompt: return error
if cron == "* * * * *": return error
if forbidden_tools: return error
if middleware.model_call_limit > 10: return error
```

**Limitations**:
- Hard to maintain
- Can't easily add new rules
- No per-user customization
- Rules are opaque to users

### GoRules Solution

**Decision Graph**:
```json
{
  "name": "flow-validation-policy",
  "rules": [
    {
      "rule_id": "max_agents_in_flow",
      "conditions": {
        "agent_count": ">5"
      },
      "action": "reject",
      "message": "Flows limited to 5 agents"
    },
    {
      "rule_id": "require_flow_input",
      "conditions": {
        "flow_input": null
      },
      "action": "reject",
      "message": "flow_input is required for context"
    },
    {
      "rule_id": "first_agent_input_marker",
      "conditions": {
        "first_agent_prompt_missing": "$input",
        "flow_input": "not_null"
      },
      "action": "reject",
      "message": "First agent system_prompt must include $input when flow_input is provided"
    },
    {
      "rule_id": "forbid_flow_tools_in_flow",
      "conditions": {
        "agent_tools": "includes_any",
        "list": ["create_flow", "run_flow", "cancel_flow", "delete_flow"]
      },
      "action": "reject",
      "message": "Flow agents may not use flow management tools (prevents recursion)"
    },
    {
      "rule_id": "cron_wildcard_forbidden",
      "conditions": {
        "schedule_type": "recurring",
        "cron_expression": "* * * * *"
      },
      "action": "reject",
      "message": "cron '* * * * *' not allowed (use schedule_type='immediate')"
    },
    {
      "rule_id": "middleware_limit",
      "conditions": {
        "middleware.model_call_limit": ">10",
        "OR": {
          "middleware.tool_call_limit": ">10"
        }
      },
      "action": "reject",
      "message": "Middleware limits must be <=10"
    },
    {
      "rule_id": "max_concurrent_flows",
      "conditions": {
        "user_tier": "free",
        "active_flows": ">3"
      },
      "action": "reject",
      "message": "Free tier limited to 3 concurrent flows"
    }
  ]
}
```

**Benefits**:
- ✅ Centralized rule management
- ✅ Explainable validation errors
- ✅ Easy to add new rules
- ✅ Per-tier customization
- ✅ No code changes for policy updates

**Implementation Priority**: ⭐⭐⭐ **HIGH** (Maintainability)

---

## ✅ Strong Fit: Dynamic Middleware Configuration

### Problem
Current middleware is static:
```python
middleware_config = FlowMiddlewareConfig.model_validate(middleware or {})
# Hard limits of <=10 for model_call_limit and tool_call_limit
```

**Limitation**: All users get same limits regardless of tier or usage patterns.

### GoRules Solution

**Decision Graph**:
```json
{
  "name": "middleware-policy",
  "rules": [
    {
      "rule_id": "free_tier_limits",
      "conditions": {
        "user_tier": "free"
      },
      "action": "set_middleware",
      "config": {
        "model_call_limit": 3,
        "tool_call_limit": 5,
        "model_retry_enabled": false,
        "tool_retry_enabled": true
      }
    },
    {
      "rule_id": "premium_tier_limits",
      "conditions": {
        "user_tier": "premium"
      },
      "action": "set_middleware",
      "config": {
        "model_call_limit": 10,
        "tool_call_limit": 10,
        "model_retry_enabled": true,
        "tool_retry_enabled": true
      }
    },
    {
      "rule_id": "enterprise_tier_limits",
      "conditions": {
        "user_tier": "enterprise"
      },
      "action": "set_middleware",
      "config": {
        "model_call_limit": null,  # No limit
        "tool_call_limit": null,   # No limit
        "model_retry_enabled": true,
        "tool_retry_enabled": true
      }
    },
    {
      "rule_id": "reduce_limits_on_high_usage",
      "conditions": {
        "monthly_cost": ">100"
      },
      "action": "adjust_middleware",
      "config": {
        "model_call_limit": 5,
        "notification": "High usage detected - limits reduced"
      }
    }
  ]
}
```

**Benefits**:
- ✅ Per-user-tier middleware
- ✅ Dynamic adjustment based on usage
- ✅ Cost control (reduce limits for high-usage users)
- ✅ No code changes for tier adjustments

**Implementation Priority**: ⭐⭐ **MEDIUM** (Nice to have)

---

## ⚠️ Moderate Fit: Agent Selection (Routing)

### Problem
Current system: LLM decides which agent to use for a task (implicit in tool selection).

**Challenge**: Similar to storage selection - natural language understanding problem.

### Current Approach (LLM)
```python
# User: "Help me research AI trends"
# LLM selects: researcher agent with search_tool, firecrawl_tool
```

### GoRules Approach (NOT Recommended ❌)

```python
# ❌ BAD: GoRules for agent routing
request = "Help me research AI trends"
intent = llm_parse_intent(request)  # Parser bottleneck!
agent = gorules_select_agent(intent)  # Low accuracy
```

**Why it fails** (based on POC):
- LLM parse is the bottleneck (76% accuracy in Phase 1)
- Natural language nuances hard to codify
- Cost/benefit doesn't justify complexity

**Better Approach** (LLM directly):
```python
# ✅ GOOD: Let LLM choose agent directly
request = "Help me research AI trends"
agents = await list_agents()
agent = await llm_select_best_agent(request, agents)
```

**Recommendation**: ❌ **Don't use GoRules for agent selection** - LLM is better at understanding intent.

**Implementation Priority**: ⭐ **LOW** (Not recommended)

---

## ⚠️ Moderate Fit: Flow Selection (Routing)

### Problem
User has multiple flows, need to decide which one to run.

**Challenge**: Again, natural language understanding problem.

### Current Approach (LLM)
```python
# User: "Run my daily briefing"
# LLM selects: "Daily Research Briefing" flow
```

### GoRules Approach (NOT Recommended ❌)

Same issue as agent selection - LLM better at understanding user intent.

**Recommendation**: ❌ **Use LLM directly for flow selection**

**Implementation Priority**: ⭐ **LOW** (Not recommended)

---

## ✅ Strong Fit: Flow Execution Guardrails

### Problem
Flows execute autonomously - need safety checks during execution.

**Current approach**: Middleware limits (model_call_limit, tool_call_limit)

**Additional GoRules checks**:
```json
{
  "name": "flow-execution-policy",
  "rules": [
    {
      "rule_id": "max_execution_time",
      "conditions": {
        "execution_time_seconds": ">300"
      },
      "action": "terminate",
      "message": "Flow exceeded maximum execution time (5 minutes)"
    },
    {
      "rule_id": "max_cost_per_flow",
      "conditions": {
        "estimated_cost": ">1.00"
      },
      "action": "require_approval",
      "message": "High-cost flow requires approval: $1.00 estimated"
    },
    {
      "rule_id": "dangerous_tool_combination",
      "conditions": {
        "tools": "includes_both",
        "list": ["delete_files", "execute_python"]
      },
      "action": "require_approval",
      "message": "Dangerous tool combination requires approval"
    },
    {
      "rule_id": "failure_rate_limit",
      "conditions": {
        "recent_failures": ">5",
        "success_rate": "<50%"
      },
      "action": "suspend",
      "message": "Flow suspended due to high failure rate - contact support"
    }
  ]
}
```

**Benefits**:
- ✅ Safety checks during autonomous execution
- ✅ Cost containment
- ✅ Explainable terminations
- ✅ Automatic suspension of problematic flows

**Implementation Priority**: ⭐⭐⭐ **HIGH** (Safety requirement for autonomous flows)

---

## ✅ Strong Fit: Resource Quotas per Agent/Flow

### Problem
Need to track and limit resource usage per agent/flow.

### GoRules Solution

```json
{
  "name": "resource-quota-policy",
  "rules": [
    {
      "rule_id": "agent_daily_quota",
      "conditions": {
        "agent_id": "*",
        "daily_executions": ">100"
      },
      "action": "throttle",
      "message": "Agent exceeded daily quota (100 executions)"
    },
    {
      "rule_id": "flow_monthly_cost_limit",
      "conditions": {
        "flow_id": "*",
        "monthly_cost": ">50.00"
      },
      "action": "throttle",
      "message": "Flow exceeded monthly cost limit ($50.00)"
    },
    {
      "rule_id": "user_total_quota",
      "conditions": {
        "user_id": "*",
        "monthly_executions": ">1000"
      },
      "action": "throttle",
      "message": "User exceeded monthly quota (1000 flow executions)"
    }
  ]
}
```

**Benefits**:
- ✅ Prevent runaway costs
- ✅ Fair resource allocation
- ✅ Per-agent/flow/user limits
- ✅ Explainable throttling

**Implementation Priority**: ⭐⭐⭐ **HIGH** (Cost control)

---

## 🎯 Recommended Implementation Pattern

### Phase 1: Add GoRules for Policy Enforcement (NOT Routing)

```python
# ❌ BAD: GoRules for understanding
agent_id = gorules_route_to_agent(user_request)  # Parser bottleneck!

# ✅ GOOD: LLM for understanding, GoRules for policy
agent_id = await llm_select_agent(user_request, agents)  # LLM understands intent
if not gorules_check_agent_access(user_id, agent_id):    # GoRules enforces policy
    return gorules_explain_why_denied(agent_id)
```

### Phase 2: Hybrid Approach

```python
# Create agent with policy check
async def create_agent_with_policy(user_id, agent_spec):
    # Step 1: LLM can help design the agent (optional)
    if user_needs_help:
        agent_spec = await llm_suggest_agent_spec(user_request)

    # Step 2: GoRules validates and enforces policy
    policy_check = gorules_validate_agent_creation(user_id, agent_spec)
    if not policy_check.allowed:
        return policy_check.message  # Explainable rejection

    # Step 3: Create agent
    return await create_agent(agent_spec)

# Run flow with guardrails
async def run_flow_with_guardrails(user_id, flow_id):
    # Step 1: Get flow spec
    flow = await get_flow(flow_id)

    # Step 2: Check execution policies
    policy_check = gorules_validate_flow_execution(user_id, flow)
    if not policy_check.allowed:
        return policy_check.message

    # Step 3: Run with monitoring
    return await run_flow_monitored(flow, policy_check.rules)
```

---

## 📊 Comparison: Current vs GoRules

| Aspect | Current (Python) | With GoRules |
|--------|------------------|--------------|
| **Agent validation** | Hard-coded if-statements | Centralized decision graph |
| **Policy updates** | Code changes | JSON updates (no redeploy) |
| **Explainability** | Generic error messages | Specific policy explanations |
| **Per-user tiers** | Manual if-tier in code | Declarative tier rules |
| **Audit trail** | None | Built-in (which rules fired) |
| **Agent routing** | LLM selects | LLM selects (unchanged) |
| **Complexity** | Low | Medium |

---

## ✅ Priority Use Cases (Implement First)

### 1. Agent Creation Policy ⭐⭐⭐

**What**: Validate agents before creation
**Rules**: Tool limits, dangerous tools, tier restrictions, output schema requirements
**Why**: Security, cost control, compliance

### 2. Flow Validation Policy ⭐⭐⭐

**What**: Validate flows before execution
**Rules**: Agent limits, tool restrictions, cron validation, middleware limits
**Why**: Prevent errors, security, stability

### 3. Flow Execution Guardrails ⭐⭐⭐

**What**: Safety checks during flow execution
**Rules**: Max execution time, cost limits, failure rate suspension
**Why**: Autonomous flow safety

### 4. Resource Quotas ⭐⭐⭐

**What**: Per-agent/flow/user usage limits
**Rules**: Daily/monthly quotas, cost thresholds
**Why**: Cost control, fair allocation

### 5. Dynamic Middleware ⭐⭐

**What**: Per-tier middleware configuration
**Rules**: Different limits for free/premium/enterprise
**Why**: Tier differentiation

---

## ❌ Not Recommended

### Agent Selection (Routing) ❌

**Why**: LLM is better at understanding user intent
**Use**: `llm_select_agent(user_request, agents)`

### Flow Selection (Routing) ❌

**Why**: Same as agent selection - natural language problem
**Use**: `llm_select_flow(user_request, flows)`

---

## 🔧 Implementation Example

### Adding GoRules to Agent Creation

```python
@tool
async def create_agent_with_policy(
    agent_id: str,
    name: str,
    description: str,
    tools: list[str],
    system_prompt: str,
    output_schema: dict | None = None,
) -> str:
    """Create agent with GoRules policy validation."""
    thread_id = _get_thread_id()
    user_tier = await get_user_tier(thread_id)

    # Build agent spec
    agent_spec = {
        "agent_id": agent_id,
        "name": name,
        "description": description,
        "tools": tools,
        "system_prompt": system_prompt,
        "output_schema": output_schema,
        "user_tier": user_tier,
        "tool_count": len(tools)
    }

    # GoRules validation
    policy_check = gorules_validate(
        graph_name="agent-creation-policy",
        input_data=agent_spec
    )

    if not policy_check.allowed:
        return f"Agent creation denied: {policy_check.message}\n" \
               f"Rule triggered: {policy_check.rule_id}"

    # Create agent if validation passes
    registry = get_agent_registry(thread_id)
    return registry.create_agent(**agent_spec)
```

---

## 💡 Key Insights from POC Applied

### Insight 1: GoRules for Policy, Not Understanding

**Lesson from storage selection POC**:
- ❌ Don't use GoRules for natural language routing
- ✅ Use GoRules for policy enforcement

**Application**:
- LLM selects which agent/flow to use
- GoRules validates if action is allowed

### Insight 2: Explainable Rejections

**Lesson from POC**: Transparency is valuable for policy enforcement.

**Application**:
```python
# Instead of:
"Error: Invalid agent"

# Use GoRules:
"Agent creation denied: Free tier limited to 3 tools (got 4)\n" \
"Rule triggered: tool_limit_free_tier"
```

### Insight 3: No Multi-Storage Complexity

**Lesson from POC**: Multi-option decisions are complex.

**Application**: Avoid multi-agent routing with GoRules. Let LLM pick one agent, then validate it.

### Insight 4: Measure Before Committing

**Lesson from POC**: Verify cost/benefit before implementing.

**Application**:
- Start with hard-coded validation (current approach)
- If policy complexity grows, add GoRules
- Don't add GoRules "just in case"

---

## 🎯 Conclusion

### YES: GoRules for Flow/Agent System

Use GoRules for:
- ✅ **Agent creation policy** (tool limits, tier restrictions, dangerous tools)
- ✅ **Flow validation** (agent limits, tool restrictions, cron validation)
- ✅ **Execution guardrails** (time limits, cost limits, failure monitoring)
- ✅ **Resource quotas** (per-agent/flow/user limits)
- ✅ **Dynamic middleware** (tier-based configuration)

### NO: GoRules for Agent/Flow Routing

Don't use GoRules for:
- ❌ **Agent selection** (LLM better at understanding intent)
- ❌ **Flow selection** (same issue - natural language problem)

### The Pattern

```python
# LLM understands user intent
agent_id = await llm_select_agent("Research AI trends", agents)

# GoRules enforces business rules
if not gorules_check_agent_access(user_id, agent_id):
    return gorules_explain_why_denied(agent_id)

# Execute
return await run_agent(agent_id)
```

**LLM for understanding, GoRules for policy.**

This is the winning pattern from the POC, and it applies perfectly to your flow/mini-agent system! 🎯
