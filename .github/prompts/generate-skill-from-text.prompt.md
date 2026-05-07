---
description: "Generate a complete SKILL.md from pasted workflow text in one shot. Use for turning raw process notes into a reusable skill with frontmatter, steps, branching logic, and quality checks."
name: "Generate Skill From Text"
argument-hint: "Paste workflow text, scope (workspace or personal), and desired depth (checklist or detailed)."
agent: "Skill Factory"
---
Generate a production-ready SKILL.md from the user text in one pass.

Requirements:
- Infer the workflow goal, ordered steps, decision points, and completion checks.
- Produce valid SKILL.md frontmatter with a discovery-friendly description.
- Include sections for purpose, when to use, inputs, procedure, decision logic, and quality gates.
- If required information is missing, make explicit assumptions instead of blocking.

Output format:
1. Final SKILL.md content as markdown.
2. Assumptions used.
3. Two to four example slash prompts to test the skill.
