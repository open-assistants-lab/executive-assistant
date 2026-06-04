---
name: skill-creation
description: Create, modify, and evaluate skills for the Executive Assistant. Use files_write to write SKILL.md files to the skills directory shown in your system prompt, then call skills_reload() to refresh the registry. You have files_write available — use it directly.
---

# Skill Creation

You create reusable skills (SKILL.md files) that teach the agent how to
handle specific tasks — research, code review, data analysis, email
templates, meeting prep, etc.

## Workflow

1. **Understand** — interview the user: what should this skill do? When
   should it trigger? What's the expected output?
2. **Write** — use `files_write` to create the SKILL.md at the skills
   directory path shown in your system prompt (<skills_dir> tag).
3. **Reload** — call `skills_reload()` so the registry picks it up.
4. **Test** — ask the user to try it, or test it yourself by invoking
   `skills_load("name")` and running a sample task.
5. **Iterate** — improve based on what worked and what didn't.

## SKILL.md Format

```yaml
---
name: my-skill
description: What it does and when to trigger. Be specific — include
  keywords and contexts the agent should match against. Make it pushy.
---

# Instructions

The body contains the skill's instructions. Be concise. Use the imperative
form. Explain WHY, not just WHAT.
```

## Key Rules

- **Files go in the skills directory** — use `files_write` to create
  `{skills_dir}/{skill-name}/SKILL.md`. The path is in your system prompt.
- **Reload after writing** — `skills_reload()` makes the new skill
  available immediately.
- **Description is the trigger** — the `description` field in frontmatter
  is how the agent decides to load this skill. Include trigger phrases.
- **Keep it lean** — SKILL.md should be under 300 lines. If it grows,
  split into referenced files.
- **Canvas forms optional** — if the user asks for a form to edit the
  skill, load `canvas-painting` and output `html:skill-form` fence block.

## Testing

After creating the skill:

1. Load it: `skills_load("name")`
2. Run a sample task and verify the output
3. If it doesn't trigger reliably, improve the description
4. Repeat until satisfied

For thorough testing, write 2-3 test prompts and run the skill against
each one. Save test cases to `{skills_dir}/{skill-name}/evals/evals.json`.

## Evaluation (Advanced)

When the user wants quantitative verification:

1. Write 2-3 test prompts as `evals/evals.json`
2. For each prompt, run the task with the skill loaded
3. Compare outputs expected vs actual
4. Aggregate results and present to the user
5. Improve based on findings

The bundled scripts in this skill directory can help automate evaluation
if the user wants rigorous testing. See `references/workflows.md`.
