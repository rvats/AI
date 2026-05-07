---
description: "Use when creating or editing any SKILL.md. Enforces skill folder naming and frontmatter validation for .github/skills, .agents/skills, and .claude/skills."
name: "Skill Folder Validation"
applyTo:
  - ".github/skills/**/SKILL.md"
  - ".agents/skills/**/SKILL.md"
  - ".claude/skills/**/SKILL.md"
---
# Skill Folder Validation

Apply these checks before finalizing any SKILL.md.

## Naming Rules
- The frontmatter `name` must exactly match the containing folder name.
- Use lowercase letters, digits, and hyphens only.
- Keep `name` length between 1 and 64 characters.

## Required Frontmatter Rules
- Frontmatter must be valid YAML wrapped with `---` markers.
- `name` is required.
- `description` is required and should use "Use when..." trigger language with clear keywords.
- Keep `description` under 1024 characters.
- Optional fields: `argument-hint`, `user-invocable`, `disable-model-invocation`.

## Body Quality Rules
- Include a clear purpose and when-to-use triggers.
- Include step-by-step procedure, not just guidance bullets.
- Include decision or branching logic for ambiguous inputs.
- Include explicit quality gates or completion checks.
- Prefer concise body content and reference external files for large details.

## Validation Routine
1. Verify folder-name and `name` match.
2. Verify required frontmatter fields are present and valid.
3. Scan for missing procedure steps or untestable quality gates.
4. Fix violations before returning final output.

## Failure Handling
- If validation fails, list each violation with a concrete fix.
- Do not mark the skill complete until all critical violations are resolved.
