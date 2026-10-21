"""Minimal chat clients with an on-disk response cache.

Model spec format  "<provider>:<model>", e.g.
  openai:gpt-5-mini                 (OPENAI_API_KEY)
  deepseek:deepseek-v4-pro          (DEEPSEEK_API_KEY, OpenAI-compatible; thinking disabled)
  qwen:qwen-max                     (DASHSCOPE_API_KEY, OpenAI-compatible)
  local:Qwen2.5-7B                  (LOCAL_BASE_URL, e.g. a vLLM server; key optional)
  localbase:allenai/OLMo-2-1124-7B  (LOCAL_BASE_URL; plain-text completion for base models
                                     without a chat template, e.g. our injection-trained models)
  custom:<model name on platform>   (CUSTOM_BASE_URL + CUSTOM_API_KEY; any OpenAI-compatible
                                     relay such as 智舵; optional CUSTOM_EXTRA_BODY as JSON)
  anthropic:claude-sonnet-5         (EXP_ANTHROPIC_API_KEY)
  mock:echo                         (offline dry run, returns the last context row)
Keys are read from environment variables; never hard-code them.
"""
import hashlib
import json
import os
import threading
import time
from pathlib import Path

from .data import BUILD

CACHE = Path(os.environ.get("CORE_CACHE_FILE", BUILD / "cache.jsonl")).resolve()

OPENAI_COMPATIBLE = {
    "openai": (None, "OPENAI_API_KEY"),   # GPT_API_KEY is accepted too (see _api_key)
    "deepseek": ("https://api.deepseek.com", "DEEPSEEK_API_KEY"),
    "qwen": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY"),
    "local": (os.getenv("LOCAL_BASE_URL"), "LOCAL_API_KEY"),
    # Any other OpenAI-compatible relay platform (e.g. 智舵): base URL and key come from .env.
    "custom": (os.getenv("CUSTOM_BASE_URL"), "CUSTOM_API_KEY"),
    # Google's OpenAI-compatible endpoint (GEMINI_API_KEY in .env). The key in use is on the free
    # tier: Pro models have no quota there, and requests may be used to improve Google's products.
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
}


def _extra_body(provider: str, model: str) -> dict | None:
    """Request extras. DeepSeek V4 thinks by default, which breaks greedy one-line probes."""
    if provider == "custom" and os.getenv("CUSTOM_EXTRA_BODY"):
        return json.loads(os.environ["CUSTOM_EXTRA_BODY"]) or None
    if provider == "local" and os.getenv("LOCAL_EXTRA_BODY"):  # e.g. vLLM + gpt-oss reasoning effort
        return json.loads(os.environ["LOCAL_EXTRA_BODY"]) or None
    if provider == "deepseek" or (provider == "custom" and "deepseek" in model.lower()):
        return {"thinking": {"type": "disabled"}}
    if provider == "custom" and "qwen" in model.lower():  # Qwen 3.x on the relay thinks by default
        return {"enable_thinking": False}
    if provider == "gemini":  # Gemini 3.x thinks by default; 3.5 Flash accepts "none" (0 reasoning tokens)
        return {"reasoning_effort": "none"}
    if provider == "openai" and model.startswith("gpt-6"):
        # gpt-6.x accepts reasoning_effort low/medium/high only (not none/minimal): low is the least
        # (63 reasoning tokens on a Hospital chunk); it also accepts no temperature but 1, see complete()
        return {"reasoning_effort": "low"}
    # GLM-5.3 on the relay cannot turn thinking off ("enable_thinking is restricted to True") and
    # by default spends >16k tokens thinking about one P2 chunk. Low effort is the least it offers
    # (~300 reasoning tokens per chunk); reasoning tokens count against max_tokens.
    if provider == "custom" and "glm" in model.lower():
        return {"reasoning_effort": "low"}
    return None


def _key(spec: str, system: str, prompt: str, max_tokens: int) -> str:
    return hashlib.sha256(json.dumps([spec, system, prompt, max_tokens]).encode()).hexdigest()


def _load_cache() -> dict:
    if not CACHE.exists():
        return {}
    with CACHE.open() as f:
        return {r["key"]: r["text"] for r in map(json.loads, f)}


_cache = _load_cache()
_write_lock = threading.Lock()  # complete() may run in threads; keep cache lines whole


def truncated(text: str) -> bool:
    """A JSON reply that did not finish: empty (a thinking model spent the whole budget on
    reasoning) or cut before the closing brace."""
    t = text.strip()
    return not t or not t.endswith(("}", "```"))


def complete_json(spec: str, prompt: str, system: str = "", max_tokens: int = 4096) -> str:
    """complete() for replies that must be whole JSON: a truncated reply is asked again with
    2x and then 4x the budget. Truncation is not evenly spread (on surrogate tables DeepSeek
    sometimes lists every cell, and GLM's reasoning runs long), so leaving cut replies in would
    lower the surrogate scores only. API models only: a vLLM server's context window leaves no
    room for a larger budget, so for local models count the truncated replies instead."""
    out = complete(spec, prompt, system=system, max_tokens=max_tokens)
    if spec.split(":", 1)[0] in ("local", "localbase", "mock"):
        return out
    for factor in (2, 4):
        if not truncated(out):
            break
        out = complete(spec, prompt, system=system, max_tokens=max_tokens * factor)
    return out


def _log_usage(spec: str, resp) -> None:
    """Token counts of each uncached API call, for cost accounting (results/usage.jsonl)."""
    u = getattr(resp, "usage", None)
    if spec.startswith("local") or u is None:
        return
    d = getattr(u, "completion_tokens_details", None)
    row = {"spec": spec, "prompt": u.prompt_tokens, "completion": u.completion_tokens,
           "reasoning": getattr(d, "reasoning_tokens", None) if d else None,
           "finish": resp.choices[0].finish_reason}
    with _write_lock, (CACHE.parent / "usage.jsonl").open("a") as f:
        f.write(json.dumps(row) + "\n")


def complete(spec: str, prompt: str, system: str = "", max_tokens: int = 512,
             stop: list[str] | None = None) -> str:
    """Greedy (temperature 0) completion, cached by (spec, system, prompt, max_tokens).
    `stop` is not part of the cache key: callers use it only to save generation time on
    outputs they cut anyway (P1 reads one line)."""
    k = _key(spec, system, prompt, max_tokens)
    if k in _cache:
        return _cache[k]
    provider, model = spec.split(":", 1)
    if provider == "mock":
        text = prompt.rstrip("\n").splitlines()[-1]
    elif provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=os.environ["EXP_ANTHROPIC_API_KEY"])
        msg = client.messages.create(
            model=model, max_tokens=max_tokens, temperature=0,
            system=system or anthropic.NOT_GIVEN,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
    elif provider in OPENAI_COMPATIBLE:
        from openai import OpenAI

        base_url, key_env = OPENAI_COMPATIBLE[provider]
        # A local mlx server that hit a GPU out-of-memory error keeps accepting requests but
        # never answers; fail after 5 minutes instead of the SDK's default ~10 min x retries.
        limits = {"timeout": 300, "max_retries": 1} if provider == "local" else {}
        key = os.getenv(key_env) or (os.getenv("GPT_API_KEY") if provider == "openai" else None) or "EMPTY"
        client = OpenAI(base_url=base_url, api_key=key, **limits)
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        extra = _extra_body(provider, model)
        # Gemini's free tier answers 429 (rate limit) and 503 ("high demand") often: wait and
        # retry for up to ~15 minutes, but not when the daily quota is used up.
        attempts = 12 if provider == "gemini" else 1
        for attempt in range(attempts):
            try:
                # gpt-6.x takes only the default temperature (1) and max_completion_tokens: its runs are
                # sampled, not greedy, unlike every other model here
                gpt6 = provider == "openai" and model.startswith("gpt-6")
                sampling = {"max_completion_tokens": max_tokens} if gpt6 else {"temperature": 0, "max_tokens": max_tokens}
                resp = client.chat.completions.create(
                    model=model, messages=messages, **sampling,
                    extra_body=extra, **({"stop": stop} if stop else {}),   # Gemini rejects "stop": null
                )
                break
            except Exception as e:  # openai.RateLimitError / InternalServerError
                status = getattr(e, "status_code", None)
                daily = "perday" in str(e).lower().replace("_", "")
                if attempt == attempts - 1 or status not in (429, 500, 503) or daily:
                    raise
                time.sleep(min(30 * (attempt + 1), 120))
        text = resp.choices[0].message.content or ""
        _log_usage(spec, resp)
    elif provider == "localbase":
        # Base models have no chat template: send raw text and let the model continue it.
        # Prompts end with a newline, so the first generated line is the model's next row.
        from openai import OpenAI

        client = OpenAI(base_url=os.getenv("LOCAL_BASE_URL"), api_key=os.getenv("LOCAL_API_KEY", "EMPTY"),
                        timeout=300, max_retries=0)
        # mlx_lm.server's stop only matches a bare "\n" token, so a base model usually writes rows
        # until max_tokens; probes read only the first line, so cap generation at about one row
        # (the prompt's last line), at ~2 characters per token.
        last_row = prompt.rstrip("\n").rsplit("\n", 1)[-1]
        resp = client.completions.create(
            model=model, prompt=(system + "\n\n" if system else "") + prompt,
            temperature=0, max_tokens=min(max_tokens, 200, len(last_row) // 2 + 20), stop=["\n"],
        )
        text = resp.choices[0].text or ""
    else:
        raise ValueError(f"unknown provider: {provider}")
    if provider != "mock":
        with _write_lock:
            _cache[k] = text
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            with CACHE.open("a") as f:
                f.write(json.dumps({"key": k, "spec": spec, "text": text}, ensure_ascii=False) + "\n")
    return text
