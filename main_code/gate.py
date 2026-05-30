from __future__ import annotations
import re
import logging
from dataclasses import dataclass
from typing import Callable


@dataclass
class RouteResult:
    route: str
    confidence: float
    source: str
    reasoning: str = ""
    expert: str = ""

    @property
    def pipeline(self) -> list[str]:
        return _PIPELINE_MAP.get(self.route, ["chat"])


_PIPELINE_MAP = {
    "bugfix":   ["locator", "generator", "verifier"],
    "codegen":  ["generator", "verifier"],
    "refactor": ["locator", "generator", "verifier"],
    "test":     ["generator", "verifier"],
    "explain":  ["chat"],
    "chat":     ["chat"],
}

_KEYWORD_ROUTES: dict[str, list[tuple[str, float]]] = {
    "bugfix": [
        (r"\u4fee\u590d|fix|bug|\u62a5\u9519|\u9519\u8bef|error|\u5d29\u6e83|crash|\u5f02\u5e38|exception|\u6539\u9519|\u51fa\u95ee\u9898\u4e86", 1.0),
        (r"\u4e0d\u884c|\u4e0d\u5bf9|\u5931\u8d25|failed|\u4e0d\u5de5\u4f5c|not working|\u574f\u4e86", 0.8),
    ],
    "codegen": [
        (r"\u5199\u4e00\u4e2a|\u521b\u5efa\u4e00\u4e2a|\u5b9e\u73b0\u4e00\u4e2a|\u65b0\u589e|\u6dfb\u52a0\u4e00\u4e2a|\u5f00\u53d1|\u751f\u6210|write|create|make|build|generate|implement|add", 1.0),
        (r"\u505a\u4e00\u4e2a|\u5f04\u4e00\u4e2a|\u6765\u4e2a|\u9700\u8981|\u5e2e\u6211\u5199", 0.7),
    ],
    "refactor": [
        (r"\u91cd\u6784|\u4f18\u5316|\u6539\u8fdb|\u91cd\u5199|\u62c6\u5206|\u6574\u7406|refactor|optimize|improve|restructure|clean", 1.0),
        (r"\u6539\u4e00\u4e0b|\u8c03\u6574|\u6539\u9020|\u91cd\u547d\u540d|rename", 0.7),
    ],
    "test": [
        (r"\u6d4b\u8bd5|\u5355\u5143\u6d4b\u8bd5|test|unittest|pytest|\u8986\u76d6\u7387|coverage|\u6d4b\u8bd5\u7528\u4f8b", 1.0),
        (r"\u9a8c\u8bc1|verify|\u68c0\u67e5\u4e00\u4e0b", 0.5),
    ],
    "explain": [
        (r"\u89e3\u91ca|\u8bf4\u660e|\u662f\u4ec0\u4e48|\u600e\u4e48\u7528|\u4e3a\u4ec0\u4e48|explain|how|what is|describe|\u5206\u6790\u4e00\u4e0b|\u4ecb\u7ecd\u4e00\u4e0b", 1.0),
        (r"\u8fd9\u6bb5\u4ee3\u7801|\u8fd9\u4e2a\u51fd\u6570|\u4ec0\u4e48\u610f\u601d|\u600e\u4e48\u770b", 0.6),
    ],
}

_KEYWORD_WEIGHT = 0.2
_AI_WEIGHT = 0.8
_HIGH_CONFIDENCE = 0.8
_MIN_CONFIDENCE = 0.3

_EXPERT_KEYWORDS: dict[str, list[str]] = {
    "fastapi": [r"fastapi", r"路由", r"接口", r"endpoint", r"api", r"依赖注入"],
    "mysql": [r"mysql", r"建表", r"索引", r"pymysql", r"sql", r"数据库"],
    "typehint": [r"类型注解", r"type hint", r"加类型", r"类型提示"],
    "nocomment": [r"删.*注释", r"去.*注释", r"去除.*注释", r"移除.*注释", r"不要.*注释", r"清理.*注释", r"去掉.*注释"],
    "docstring": [r"加注释", r"写注释", r"增加注释", r"添加注释", r"docstring"],
}


def _keyword_score(text: str) -> dict[str, float]:
    scores: dict[str, float] = {}
    for route, patterns in _KEYWORD_ROUTES.items():
        best = 0.0
        for pattern, weight in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                matches = list(re.finditer(pattern, text, re.IGNORECASE))
                match_count = len(matches)
                score = weight * (0.7 + 0.3 * min(1.0, match_count / 3))
                best = max(best, score)
        scores[route] = best
    if all(v < 0.1 for v in scores.values()):
        scores["chat"] = 0.5
    else:
        scores.setdefault("chat", 0.0)
    return scores


def classify(
    user_input: str,
    llm_classify: Callable[[str, list[str]], dict[str, float]] | None = None,
) -> RouteResult:
    text = user_input.strip()
    if not text:
        return RouteResult(route="chat", confidence=1.0, source="keyword",
                          reasoning="")

    kw_scores = _keyword_score(text)
    top_route = max(kw_scores, key=kw_scores.get)
    top_score = kw_scores[top_route]
    expert = _detect_expert(text)

    if top_score >= _HIGH_CONFIDENCE:
        return RouteResult(
            route=top_route,
            confidence=top_score,
            source="keyword",
            reasoning=f"{top_route} ({top_score:.2f})",
            expert=expert,
        )

    if not llm_classify:
        if top_score >= _MIN_CONFIDENCE:
            return RouteResult(
                route=top_route,
                confidence=top_score,
                source="keyword",
                reasoning=f"{top_route} ({top_score:.2f})",
                expert=expert,
            )
        return RouteResult(
            route="chat", confidence=0.5, source="keyword",
            reasoning="fallback", expert=expert,
        )

    if llm_classify:
        try:
            ai_scores = llm_classify(text, list(_KEYWORD_ROUTES.keys()) + ["chat"])
        except Exception:
            ai_scores = {}

        all_routes = set(list(kw_scores.keys()) + list(ai_scores.keys()))
        combined: dict[str, float] = {}
        for route in all_routes:
            kw = kw_scores.get(route, 0.0)
            ai = ai_scores.get(route, 0.0)
            combined[route] = kw * _KEYWORD_WEIGHT + ai * _AI_WEIGHT

        best_route = max(combined, key=combined.get)
        best_score = combined[best_route]

        if best_score >= _MIN_CONFIDENCE:
            return RouteResult(
                route=best_route,
                confidence=best_score,
                source="hybrid",
                reasoning=f"kw({kw_scores.get(best_route,0):.2f})*0.2 + ai({ai_scores.get(best_route,0):.2f})*0.8",
                expert=expert,
            )

    return RouteResult(
        route="chat",
        confidence=0.5,
        source="keyword",
        reasoning="fallback",
        expert=expert,
    )


def _detect_expert(text: str) -> str:
    for name, patterns in _EXPERT_KEYWORDS.items():
        for p in patterns:
            if re.search(p, text, re.IGNORECASE):
                return name
    return ""


def classify_multi(
    user_input: str,
    llm_classify_steps,
    cfg,
) -> list[RouteResult]:
    text = user_input.strip()
    if not text:
        return [RouteResult(route="chat", confidence=1.0, source="keyword", reasoning="empty")]
    kw_scores = _keyword_score(text)
    data = llm_classify_steps(text, cfg)
    is_compound = data.get("is_compound", False)
    steps = data.get("steps", [])
    results: list[RouteResult] = []
    for step in steps:
        route = step.get("route", "chat")
        if route not in _PIPELINE_MAP:
            route = "chat"
        expert = step.get("expert", "")
        if not expert:
            expert = _detect_expert(step.get("task", text))
        ai_score = 1.0 if is_compound else 1.0
        kw = kw_scores.get(route, 0.0)
        combined = kw * _KEYWORD_WEIGHT + ai_score * _AI_WEIGHT
        results.append(RouteResult(
            route=route,
            confidence=min(1.0, combined),
            source="ai_multi" if is_compound else "ai",
            reasoning=f"kw({kw:.2f})*0.2 + ai(1.0)*0.8 | task: {step.get('task', text)[:80]}",
            expert=expert,
        ))
    _save_route_log(text, results, data, cfg)
    return results if results else [RouteResult(route="chat", confidence=0.5, source="keyword", reasoning="fallback")]


def _save_route_log(original_input: str, results: list[RouteResult], raw_data: dict, cfg) -> None:
    import json
    import platform
    import sys
    from datetime import datetime, timezone, timedelta
    from pathlib import Path
    cst = timezone(timedelta(hours=8))
    now = datetime.now(cst)
    filename = now.strftime("%Y%m%d_%H%M%S_%f") + ".json"
    log_dir = Path(__file__).parent.parent / "ROU_TN"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / filename
    record = {
        "timestamp": now.isoformat(),
        "os": f"{platform.system()} {platform.release()}",
        "python": sys.version.split()[0],
        "input": original_input,
        "is_compound": raw_data.get("is_compound", False),
        "steps": [
            {
                "route": r.route,
                "expert": r.expert,
                "confidence": round(r.confidence, 4),
                "source": r.source,
                "reasoning": r.reasoning,
                "task": raw_data.get("steps", [{}])[i].get("task", original_input) if i < len(raw_data.get("steps", [])) else original_input,
            }
            for i, r in enumerate(results)
        ],
        "raw_response": raw_data,
    }
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    logger = logging.getLogger("jcode.gate")
    logger.info(f"route log saved: {filename}")
