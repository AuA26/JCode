from __future__ import annotations
import httpx
import logging
from .config import Config

logger = logging.getLogger("jcode.llm")

PROVIDER_TEMPLATES = {
    "ollama": {
        "chat_url": "/api/chat",
        "headers": lambda cfg: {"Content-Type": "application/json"},
    },
    "deepseek": {
        "chat_url": "/v1/chat/completions",
        "headers": lambda cfg: {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg.api_key}",
        },
    },
}


def _build_ollama_payload(
    messages: list[dict],
    cfg: Config,
    system_prompt: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict:
    msgs = list(messages)
    if system_prompt:
        msgs.insert(0, {"role": "system", "content": system_prompt})
    return {
        "model": cfg.model,
        "messages": msgs,
        "stream": False,
        "options": {
            "temperature": temperature if temperature is not None else cfg.temperature,
            "num_predict": max_tokens or cfg.max_tokens,
        },
    }


def _build_openai_payload(
    messages: list[dict],
    cfg: Config,
    system_prompt: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict:
    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)
    return {
        "model": cfg.model,
        "messages": full_messages,
        "temperature": temperature if temperature is not None else cfg.temperature,
        "max_tokens": max_tokens or cfg.max_tokens,
    }


def chat(
    messages: list[dict],
    cfg: Config,
    system_prompt: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    if not cfg.is_configured:
        raise RuntimeError("API not configured")

    template = PROVIDER_TEMPLATES.get(cfg.provider)
    if not template:
        raise ValueError(f"unknown provider: {cfg.provider}")

    url = cfg.base_url.rstrip("/") + template["chat_url"]
    headers = template["headers"](cfg)

    if cfg.provider == "ollama":
        payload = _build_ollama_payload(messages, cfg, system_prompt, temperature, max_tokens)
    else:
        payload = _build_openai_payload(messages, cfg, system_prompt, temperature, max_tokens)

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=120.0)
        resp.raise_for_status()
        data = resp.json()
        if cfg.provider == "ollama":
            return data["message"]["content"]
        return data["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        logger.error(f"API error {e.response.status_code}: {e.response.text[:300]}")
        raise RuntimeError(f"API request failed ({e.response.status_code})") from e
    except httpx.RequestError as e:
        logger.error(f"network error: {e}")
        raise RuntimeError(f"cannot connect: {cfg.base_url}") from e


def classify(
    user_input: str,
    labels: list[str],
    cfg: Config,
) -> dict[str, float]:
    labels_text = ", ".join(labels)
    prompt = (
        f"Classify. Score each (0-1). JSON only.\n"
        f"Categories: {labels_text}\n"
        f"Input: {user_input}\n"
        f"JSON:"
    )

    result = chat(
        messages=[{"role": "user", "content": prompt}],
        cfg=cfg,
        temperature=0.0,
        max_tokens=200,
    )

    try:
        import json
        result = result.strip().strip("`").strip()
        if result.startswith("json"):
            result = result[4:]
        scores = json.loads(result)
        return {k: max(0.0, min(1.0, float(v))) for k, v in scores.items() if k in labels}
    except (json.JSONDecodeError, ValueError):
        logger.warning(f"classify parse failed: {result[:200]}")
        return {}
