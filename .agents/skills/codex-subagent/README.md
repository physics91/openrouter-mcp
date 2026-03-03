Leave a star if you like it

# Codex Subagent for Claude Code (bugi-backend)

## Purpose
Enable Claude Code to invoke the Codex CLI (`codex exec` and session resumes) for automated code analysis, refactoring, and editing workflows on the `~/dev/bugi-backend` project.

## Prerequisites
- `codex` CLI installed and available on `PATH`.
- Codex configured with valid credentials and settings.
- Confirm the installation by running `codex --version`; resolve any errors before using the skill.

## Usage

### Important: Thinking Tokens
By default, this skill suppresses thinking tokens (stderr output) using `2>/dev/null` to avoid bloating Claude Code's context window. If you want to see the thinking tokens for debugging or insight into Codex's reasoning process, explicitly ask Claude to show them.

### Example Workflow

**User prompt:**
```
Use codex to analyze bugi-backend and suggest improvements.
```

**Claude Code response:**
Claude will activate the Codex Subagent skill and:
1. Ask which model to use unless already specified in your prompt.
2. Ask which reasoning effort level (`low`, `medium`, or `high`) unless already specified in your prompt.
3. Select appropriate sandbox mode (defaults to `read-only` for analysis)
4. Run a command like:
```bash
codex exec -m gpt-5.2 \
  --config model_reasoning_effort="high" \
  --sandbox read-only \
  --full-auto \
  --skip-git-repo-check \
  -C ~/dev/bugi-backend \
  "Analyze this repository comprehensively..." 2>/dev/null
```

**Result:**
Claude will summarize the Codex analysis output, highlighting key suggestions and asking if you'd like to continue with follow-up actions.

### Detailed Instructions
See `SKILL.md` for complete operational instructions, CLI options, and workflow guidance.
