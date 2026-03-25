# Session Prompt: Retry Limits with AI Advisor Escalation

## Context

This session uses a **three-tier escalation model** when code fails:

```
Tier 1: Self-fix     (up to 3 attempts)
Tier 2: AI Advisor   (consult a different model for a second opinion)
Tier 3: Ask User     (stop and present findings)
```

A behavioral adjustment is already active enforcing retry limits.
This prompt adds Tier 2 — consulting a second AI model before bothering the user.

---

## Escalation Protocol

### Tier 1 — Self-fix (attempts 1-3)

When writing or testing code and an error occurs:

| Attempt | Action |
|---------|--------|
| 1 | Fix the obvious issue, re-run |
| 2 | If same error → change approach. If different error → fix and re-run |
| 3 | If still failing → STOP coding. Move to Tier 2 |

**Rules:**
- Same error twice = the approach is wrong, not the syntax
- Environment/infra issues (service unreachable, container not running) = skip to Tier 3 immediately
- Fundamentally wrong approach (wrong container, wrong architecture) = skip to Tier 3 immediately

### Tier 2 — Consult AI Advisor

After 3 failed attempts, before asking the user, consult the advisor model:

```bash
python /a0/usr/ask_advisor.py \
    --task "<what you were trying to do>" \
    --tried "<what you tried — all 3 attempts summarized>" \
    --errors "<the errors you got>"
```

Or for complex context, write a markdown file and pass it:

```bash
cat > /tmp/advisor_context.md << 'CONTEXT'
## Task
<detailed description of what you were trying to do>

## Attempt 1
<what you did, what happened>

## Attempt 2
<what you changed, what happened>

## Attempt 3
<what you changed, what happened>

## Environment
- Container: Agent Zero (Kali Linux)
- Services: doc-parser on :5000, Hono API on :3000, Supabase on :54321
- Key constraint: doc-parser is a separate Docker container, do NOT install packages in it

## What should I do differently?
CONTEXT

python /a0/usr/ask_advisor.py --context-file /tmp/advisor_context.md
```

**After receiving advisor response:**

| Advisor says | Action |
|-------------|--------|
| Specific fix or different approach | Try it (this counts as attempt 4 — you get ONE shot) |
| "This is an infra/environment issue" | Move to Tier 3 — notify user |
| "I don't know" or vague advice | Move to Tier 3 — notify user |
| Advisor call itself fails | Move to Tier 3 — notify user |

**You get exactly ONE attempt with the advisor's suggestion.** If it fails, move to Tier 3.

### Tier 3 — Ask User

Present a structured summary:

```
## Stuck: <brief title>

### Task
<what you were trying to do>

### Attempts (self)
1. <what you tried> → <what happened>
2. <what you tried> → <what happened>
3. <what you tried> → <what happened>

### Advisor consultation
- Model: <which model>
- Advice: <what it suggested>
- Result: <what happened when you tried it>

### My assessment
<your best guess at the root cause>

### Options I see
A. <option>
B. <option>
C. <something the user might need to do on their end>
```

---

## Advisor Configuration

**Config file:** `/a0/usr/advisor-config.yml`

The advisor model defaults to `google/gemini-2.5-pro` via OpenRouter.
To change the model, edit the config file:

```yaml
advisor:
  model: "google/gemini-2.5-pro"       # default
  # model: "anthropic/claude-sonnet-4"  # alternative
  # model: "deepseek/deepseek-r1"      # alternative
  # model: "openai/o3-mini"            # alternative
  max_tokens: 4096
  temperature: 0.3
```

The script uses the same `OPENROUTER_API_KEY` from `/a0/usr/.env`.
No additional API keys needed.

**Script location:** `/a0/usr/ask_advisor.py`

**Override model on the fly:**
```bash
python /a0/usr/ask_advisor.py --model "deepseek/deepseek-r1" \
    --task "..." --tried "..." --errors "..."
```

---

## Quick Reference: When to use each tier

| Situation | Tier |
|-----------|------|
| Syntax error, typo, missing import | Tier 1 (self-fix) |
| Logic error, wrong approach after 3 tries | Tier 2 (advisor) |
| Service not running, container issue | Tier 3 (user) — immediately |
| Permission denied, missing credentials | Tier 3 (user) — immediately |
| Advisor gives a good suggestion that fails | Tier 3 (user) |
| Advisor is unreachable or errors out | Tier 3 (user) |
| Fundamental architecture question | Tier 3 (user) — immediately |

---

## Files created for this workflow

| File | Location | Persistent? |
|------|----------|-------------|
| Advisor config | `/a0/usr/advisor-config.yml` | Yes (bind mount) |
| Advisor script | `/a0/usr/ask_advisor.py` | Yes (bind mount) |
| Behavioral adjustment | Agent Zero behavior system | Yes (across sessions) |
| System prompt edit | `/a0/prompts/agent.system.main.solving.md` | No (container only) |

---

## To activate in a new session

Paste this prompt at the start of a new conversation, or reference it:

> Read `/a0/usr/workdir/advisor-escalation-prompt.md` and follow the
> three-tier escalation protocol for all coding tasks in this session.

The behavioral adjustment (Tier 1 limits) is already persistent.
This prompt adds Tier 2 (advisor consultation) on top.
