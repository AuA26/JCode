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


_MULTI_CLASSIFY_PROMPT = """You are a router. Your ONLY job: output a JSON object. Start with { and end with }. No markdown, no explanation, no code fences, no leading text.

Routes: codegen(create/write code), bugfix(fix error/crash), refactor(improve/restructure), test(write/run tests), explain(analyze/comment/docstring), chat(talk)

Experts (optional): fastapi, mysql, typehint, nocomment, docstring
nocomment=remove/strip comments; docstring=add docstrings/comments

Compound detection keywords: 并 并且 然后 接着 同时 之后 再 还有 以及 and then after

Examples:
"写个贪吃蛇" → {"is_compound":false,"steps":[{"route":"codegen","task":"写个贪吃蛇","expert":""}]}
"生成代码并加注释" → {"is_compound":true,"steps":[{"route":"codegen","task":"生成代码","expert":""},{"route":"explain","task":"加注释","expert":"docstring"}]}
"删除所有注释" → {"is_compound":false,"steps":[{"route":"refactor","task":"删除所有注释","expert":"nocomment"}]}
"修复bug然后写测试" → {"is_compound":true,"steps":[{"route":"bugfix","task":"修复bug","expert":""},{"route":"test","task":"写测试","expert":""}]}
"这个函数是什么意思" → {"is_compound":false,"steps":[{"route":"explain","task":"这个函数是什么意思","expert":""}]}

Rules:
1. is_compound=true only when multiple actions detected via compound keywords
2. Logical order: codegen before explain, bugfix before test, explain before refactor
3. For "注释/写注释/加注释" → route=explain expert=docstring
4. For "保存到/输出到/放到" → ignore, it's a file path hint, not a separate step

Input: """


def _extract_json(text: str) -> str:
    import re
    text = text.strip()
    m = re.search(r'\{[\s\S]*\}', text)
    if m:
        return m.group(0)
    return text


def classify_steps(user_input: str, cfg: Config) -> dict:
    result = chat(
        messages=[{"role": "user", "content": _MULTI_CLASSIFY_PROMPT + user_input}],
        cfg=cfg,
        temperature=0.2,
        max_tokens=300,
    )
    data = _parse_steps_response(result, user_input)
    if data.get("steps"):
        return data
    retry = chat(
        messages=[{"role": "user", "content": _MULTI_CLASSIFY_PROMPT + user_input + "\n{"}],
        cfg=cfg,
        temperature=0.1,
        max_tokens=250,
    )
    return _parse_steps_response("{" + retry, user_input)


def _parse_steps_response(result: str, user_input: str) -> dict:
    import json
    text = _extract_json(result)
    text = text.strip().strip("`").strip()
    if text.startswith("json"):
        text = text[4:].strip()
    if not text:
        logger.warning(f"classify_steps parse failed: empty after extraction")
        print(f"  LLM路由不成功，执行关键词路由")
        return _keyword_fallback_route(user_input)
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("not a dict")
        data.setdefault("is_compound", False)
        data.setdefault("steps", [])
        if not data["steps"]:
            data["steps"] = [{"route": "chat", "task": user_input, "expert": ""}]
        return data
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.debug(f"classify_steps parse failed: {e} | raw={result[:200]}")
        return _keyword_fallback_route(user_input)


def _keyword_fallback_route(user_input: str) -> dict:
    import re
    kw_map = [
        (r"写|创建|生成|实现|新增|write|create|generate|implement|做|弄|来", "codegen"),
        (r"修复|fix|bug|报错|错误|error|崩溃|crash|异常|exception", "bugfix"),
        (r"重构|优化|改进|重写|拆分|整理|refactor|optimize|clean", "refactor"),
        (r"测试|unittest|pytest|test|覆盖率|coverage", "test"),
        (r"解释|说明|是什么|怎么用|为什么|分析|注释|docstring|介绍", "explain"),
    ]
    for pattern, route in kw_map:
        if re.search(pattern, user_input, re.IGNORECASE):
            return {"is_compound": False, "steps": [{"route": route, "task": user_input, "expert": ""}]}
    return {"is_compound": False, "steps": [{"route": "chat", "task": user_input, "expert": ""}]}
