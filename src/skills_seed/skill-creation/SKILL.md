---
name: skill-creation
description: Create, modify, test, and evaluate skills for the Executive Assistant. Use files_write to write SKILL.md files to the skills directory shown in your system prompt, then call skills_reload() to refresh the registry. You have files_write available — use it directly.
---

# Skill Creation

You create reusable skills (SKILL.md files) that teach the agent how to
handle specific tasks — research, code review, data analysis, email
templates, etc.

## Workflow

1. **Understand** — interview the user: what should this skill do? When
   should it trigger? What's the expected output?
2. **Write** — use `files_write` to create the SKILL.md at the skills
   directory path shown in your system prompt.
3. **Reload** — call `skills_reload()` so the registry picks it up.
4. **Test** — see Evaluation below.
5. **Iterate** — improve based on results, repeat.

## SKILL.md Format

```yaml
---
name: my-skill
description: What it does and when to trigger. Be specific — include
  trigger phrases and contexts. Make it pushy.
---

# Instructions

The body contains the skill's instructions. Be concise. Use imperative
form. Explain WHY, not just WHAT.
```

- **Description is the trigger** — the `description` field in frontmatter
  is how the agent decides to load this skill. Include keywords.
- **Keep it lean** — under 300 lines. Split into referenced files if
  larger.

---

## Evaluation Pipeline

This is how we verify a skill actually works. The workflow:

```
Write test cases → Run with/without skill → Grade → Review → Iterate
```

### Step 1: Write Test Cases

Create 2-3 realistic prompts the user would actually say. Save to
`{skill_dir}/evals/evals.json`:

```json
{
  "skill_name": "company-research",
  "evals": [
    {"id": 1, "prompt": "Research Tesla competitors in EV market"},
    {"id": 2, "prompt": "Analyze Apple supply chain risks"},
    {"id": 3, "prompt": "Compare Coca-Cola and PepsiCo business models"}
  ]
}
```

### Step 2: Run Tests

For each test case, run TWO executions in parallel via `subagent_start`:

**With-skill run:**
```
subagent_start("research-assistant", "first load skills_load('name'), then: <prompt>")
```

**Baseline run** (no skill):
```
subagent_start("research-assistant", "<prompt>")
```

Save outputs to: `{skill_dir}-workspace/iteration-1/eval-{N}/{with_skill,baseline}/output.md`

Capture timing: record `duration_ms` and `total_tokens` from each result
in a `timing.json` per run.

### Step 3: Grade

For each test case, compare with-skill vs baseline:

1. Does the with-skill output meet the expected criteria?
2. Is it better/faster/cheaper than baseline?
3. Record pass/fail with evidence in `grading.json`:

```json
{
  "eval_id": 1,
  "assertions": [
    {"text": "Output includes competitor names", "passed": true, "evidence": "Found Tesla, BYD, Rivian"},
    {"text": "Output includes SWOT elements", "passed": false, "evidence": "No threats section found"}
  ]
}
```

### Step 4: Aggregate

Create a `benchmark.json` summary:

```json
{
  "skill_name": "company-research",
  "iteration": 1,
  "pass_rate": 0.67,
  "time": {"with_skill": {"mean_ms": 12000, "stddev_ms": 2000}, "baseline": {"mean_ms": 15000, "stddev_ms": 3000}},
  "tokens": {"with_skill": {"mean": 5000, "stddev": 800}, "baseline": {"mean": 6000, "stddev": 1000}}
}
```

### Step 5: Review with User

Present the benchmark and outputs. Use `canvas-painting` to render a
comparison card:

1. Load `canvas-painting` skill
2. Generate an HTML comparison card showing benchmark table + per-test
   outputs side by side
3. User reviews, provides feedback

### Step 6: Iterate

Based on feedback, improve the skill and run `iteration-2/`, `iteration-3/`,
etc. Stop when:
- User is satisfied
- All assertions pass
- No meaningful improvement

---

## Key Rules

- **Files go in the skills directory** — write to `{skills_dir}/{skill-name}/SKILL.md`
- **Reload after writing** — `skills_reload()` after creating or editing
- **Workspace beside the skill** — save eval results to `{skill-name}-workspace/` as a sibling of the skill directory
- **Parallel runs** — spawn with-skill and baseline in the same turn via `subagent_start`
- **Canvas for review** — use `canvas-painting` to render the benchmark comparison
