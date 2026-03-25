#!/usr/bin/env python3
"""ask_advisor.py — Consult a second AI model for advice when stuck.

Usage:
    python /a0/usr/ask_advisor.py \
        --task "What I was trying to do" \
        --tried "What I tried (attempt 1, 2, 3...)" \
        --errors "The errors I got"

    # Or pipe a detailed context file:
    python /a0/usr/ask_advisor.py --context-file /tmp/stuck_context.md

Reads config from /a0/usr/advisor-config.yml
Reads API key from /a0/usr/.env (OPENROUTER_API_KEY)
"""
import argparse
import json
import os
import sys

try:
    import yaml
except ImportError:
    yaml = None

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)


DEFAULT_CONFIG = {
    "model": "google/gemini-2.5-pro",
    "max_tokens": 4096,
    "temperature": 0.3,
    "system_prompt": (
        "You are a senior software engineering advisor. Another AI agent is stuck "
        "on a task and is consulting you for a second opinion.\n\n"
        "You will receive the task, what was tried, and the errors.\n"
        "Identify the root cause, suggest a different approach, be specific with "
        "commands/code/paths. If it is an environmental issue, say so clearly. "
        "If you do not know, say so. Be concise."
    ),
}


def load_config():
    """Load advisor config from YAML, falling back to defaults."""
    config_path = "/a0/usr/advisor-config.yml"
    cfg = dict(DEFAULT_CONFIG)

    if os.path.exists(config_path) and yaml:
        with open(config_path) as f:
            raw = yaml.safe_load(f) or {}
        adv = raw.get("advisor", raw)
        for key in ("model", "max_tokens", "temperature", "system_prompt"):
            if key in adv:
                cfg[key] = adv[key]
    elif os.path.exists(config_path) and not yaml:
        print("WARN: pyyaml not installed, using defaults. pip install pyyaml", file=sys.stderr)

    return cfg


def get_api_key():
    """Read OpenRouter API key from environment or .env file."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key

    env_path = "/a0/usr/.env"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("OPENROUTER_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("''")

    print("ERROR: OPENROUTER_API_KEY not found in env or /a0/usr/.env", file=sys.stderr)
    sys.exit(1)


def ask_advisor(task: str, tried: str, errors: str, cfg: dict, api_key: str) -> str:
    """Send the stuck-context to the advisor model and return advice."""
    user_message = f"""## Task
{task}

## What was tried
{tried}

## Errors encountered
{errors}

## What should I do differently?"""

    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://agent-zero.local",
            "X-Title": "Agent Zero Advisor",
        },
        json={
            "model": cfg["model"],
            "max_tokens": cfg["max_tokens"],
            "temperature": cfg["temperature"],
            "messages": [
                {"role": "system", "content": cfg["system_prompt"]},
                {"role": "user", "content": user_message},
            ],
        },
        timeout=120,
    )

    if resp.status_code != 200:
        return f"ADVISOR ERROR {resp.status_code}: {resp.text[:500]}"

    data = resp.json()
    choices = data.get("choices", [])
    if not choices:
        return f"ADVISOR ERROR: No choices in response. Raw: {json.dumps(data)[:500]}"

    return choices[0]["message"]["content"]


def main():
    parser = argparse.ArgumentParser(description="Consult AI advisor when stuck")
    parser.add_argument("--task", default="", help="What you were trying to do")
    parser.add_argument("--tried", default="", help="What you tried so far")
    parser.add_argument("--errors", default="", help="Errors encountered")
    parser.add_argument("--context-file", default="", help="Path to a markdown file with full context")
    parser.add_argument("--model", default="", help="Override advisor model")
    args = parser.parse_args()

    cfg = load_config()
    api_key = get_api_key()

    if args.model:
        cfg["model"] = args.model

    if args.context_file:
        with open(args.context_file) as f:
            content = f.read()
        task = content
        tried = ""
        errors = ""
    else:
        task = args.task
        tried = args.tried
        errors = args.errors

    if not task and not tried and not errors:
        print("ERROR: Provide --task/--tried/--errors or --context-file", file=sys.stderr)
        sys.exit(1)

    print(f"Consulting advisor: {cfg['model']}...", file=sys.stderr)
    advice = ask_advisor(task, tried, errors, cfg, api_key)
    print(advice)


if __name__ == "__main__":
    main()
