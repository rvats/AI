---
name: create-skill
description: 'Create or refine a reusable SKILL.md from conversation workflows. Use when turning repeated methods into slash-invocable skills with steps, branching, and validation checks.'
argument-hint: 'Describe the workflow to turn into a skill, desired scope, and level of detail.'
user-invocable: true
---

# Create Skill

## Purpose
Turn a repeated conversation workflow into a production-ready SKILL.md that can be invoked on demand.

## When to Use
- You have a repeatable method used across tasks and want to package it.
- You want a slash-invocable workflow with clear steps and decision points.
- You want consistency checks so generated skills are practical and discoverable.

## Inputs
- Conversation history or a written workflow description.
- Desired scope: workspace-scoped or personal.
- Desired depth: quick checklist or full multi-step workflow.

## Procedure
1. Extract workflow signals from the conversation.
   - Capture ordered steps, branches, and decision triggers.
   - Capture quality criteria and completion checks.
2. Decide if clarification is required.
   - If no clear workflow appears, ask:
     - What outcome should this skill produce?
     - Should it be workspace-scoped or personal?
     - Should it be a quick checklist or a full multi-step workflow?
3. Draft SKILL.md.
   - Use valid frontmatter with a keyword-rich description.
   - Include "when to use", procedure, and explicit validation checks.
   - Keep body concise and move heavy content to referenced files when needed.
4. Save in the correct location.
   - Workspace: .github/skills/<name>/SKILL.md
   - Personal: ~/.copilot/skills/<name>/SKILL.md
5. Critique draft for ambiguity.
   - Identify the weakest or least testable steps.
   - Ask focused follow-up questions only for those weak spots.
6. Finalize and hand off.
   - Summarize what the skill produces.
   - Provide 3 to 5 example prompts to test it.
   - Propose related customizations to create next.

## Decision Logic
- If the workflow is stable and repeatable, create a skill.
- If the task is a single one-off instruction with arguments, prefer a prompt.
- If always-on behavior is desired across most tasks, prefer instructions.

## Quality Gates
- Name matches folder name and uses lowercase plus hyphens.
- Description includes trigger keywords for discovery.
- SKILL.md includes step-by-step procedure with decision points.
- Completion criteria are explicit and testable.
- File location matches chosen scope.

## Output Contract
A finalized SKILL.md that includes:
- Clear use cases and trigger phrases.
- Ordered procedure with branching logic.
- Validation checklist.
- Example prompts for immediate trial.
- Suggested next customizations.
