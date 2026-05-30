from __future__ import annotations
import sys
import json
import time
import logging
import httpx
from pathlib import Path
from dataclasses import dataclass, asdict
from .tui import select

try:
    import ollama as _ollama
except ImportError:
    _ollama = None

logging.getLogger("httpx").setLevel(logging.WARNING)
CONFIG_PATH = Path(__file__).parent.parent / "config.json"
RED = "\033[31m"
GREEN = "\033[32m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"

@dataclass
class Config:
    provider: str = ""
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    temperature: float = 0.3
    max_tokens: int = 4096

    @property
    def is_configured(self) -> bool:
        return bool(self.provider and self.model and self.base_url)

def _detect_first_run() -> bool:
    if not CONFIG_PATH.exists():
        return True
    try:
        cfg = load_config()
        return not cfg.is_configured
    except Exception:
        return True

def load_config() -> Config:
    if not CONFIG_PATH.exists():
        return Config()
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Config(**{k: v for k, v in data.items() if k in Config.__dataclass_fields__})

def save_config(cfg: Config) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, indent=2, ensure_ascii=False)

def _check_ollama_running() -> bool:
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False

def _list_ollama_models() -> list[str]:
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=5)
        data = r.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []

def _pull_ollama(model: str) -> bool:
    print(f"\n  {CYAN}下载 {model}...{RESET}")
    if _ollama is None:
        print(f"  {RED}请安装 ollama: pip install ollama{RESET}")
        return False
    try:
        for chunk in _ollama.pull(model, stream=True):
            if hasattr(chunk, "completed") and hasattr(chunk, "total") and chunk.total:
                done, total = chunk.completed, chunk.total
                if total > 0:
                    pct = round(done / total * 100, 1)
                    bar = int(pct // 2)
                    sys.stdout.write(f"\r  [{GREEN}{'█' * bar}{' ' * (50 - bar)}{RESET}] {pct}%  ")
                    sys.stdout.flush()
            if hasattr(chunk, "status") and chunk.status == "success":
                break
        sys.stdout.write("\n")
        sys.stdout.flush()
        time.sleep(0.5)
        if model in _list_ollama_models():
            print(f"  {GREEN}✓ 下载完成{RESET}")
            return True
    except Exception as e:
        msg = str(e)
        if "newer version" in msg.lower() or "412" in msg:
            print(f"\n  {RED}Ollama 版本过旧，请升级:{RESET} {CYAN}https://ollama.com/download{RESET}")
        else:
            print(f"\n  {RED}下载失败: {e}{RESET}")
    return False

_PRESET_MODELS = ["gemma4", "qwen3.6", "qwen3.5", "deepseek-r1"]
_SIZE_MAP = {
    "gemma4": ["e4b", "26b", "31b"],
    "qwen3.5": ["9b", "27b", "35b"],
    "qwen3.6": ["27b", "35b"],
    "deepseek-r1": ["14b", "32b"],
}

def _setup_ollama_remote(cfg: Config) -> Config:
    print()
    addr = input(f"  {CYAN}服务器地址 (IP:PORT){RESET} (例: 192.168.1.100:11434): ").strip()
    if not addr:
        print(f"  {RED}地址不能为空{RESET}")
        return _setup_ollama_remote(cfg)
    model = input(f"  {CYAN}服务器上的模型名称{RESET}: ").strip()
    if not model:
        print(f"  {RED}模型名不能为空{RESET}")
        return _setup_ollama_remote(cfg)
    cfg.provider = "ollama"
    cfg.base_url = f"http://{addr}"
    cfg.model = model
    cfg.api_key = "ollama"
    save_config(cfg)
    print(f"  {GREEN}✓{RESET} provider=ollama model={model}")
    return cfg

def _pick_ollama_model(cfg: Config) -> Config | None:
    models = _list_ollama_models()
    if models:
        choice = select(models, f"{CYAN}已安装的模型:{RESET}")
        if choice == -1:
            return None
        cfg.model = models[choice]
    else:
        family_choice = select(_PRESET_MODELS, f"{CYAN}选择模型系列:{RESET}")
        if family_choice == -1:
            return None
        family = _PRESET_MODELS[family_choice]
        sizes = _SIZE_MAP[family]
        size_choice = select(sizes, f"{CYAN}选择 {family} 参数量:{RESET}")
        if size_choice == -1:
            return _pick_ollama_model(cfg)
        model_tag = f"{family}:{sizes[size_choice]}"
        if _pull_ollama(model_tag):
            cfg.model = model_tag
        else:
            models = _list_ollama_models()
            if models:
                choice = select(models, f"{CYAN}已安装的模型:{RESET}")
                if choice == -1:
                    return None
                cfg.model = models[choice]
            else:
                print(f"  {RED}下载失败，请检查 ollama 状态{RESET}")
                input(f"  按 Enter 重试...")
                return _pick_ollama_model(cfg)
    cfg.provider = "ollama"
    cfg.base_url = "http://localhost:11434"
    cfg.api_key = "ollama"
    save_config(cfg)
    print(f"  {GREEN}✓{RESET} provider=ollama model={cfg.model}")
    return cfg

def _setup_ollama_local(cfg: Config) -> Config | None:
    print(f"\n  检测 Ollama 服务...")
    if not _check_ollama_running():
        print(f"\n  {RED}{BOLD}未检测到 Ollama 服务，请确保已安装并启动{RESET}")
        print(f"  安装: https://ollama.com")
        print(f"  启动: ollama serve")
        input(f"\n  按 Enter 重试...")
        return _setup_ollama_local(cfg)
    print(f"  {GREEN}✓ Ollama 已运行{RESET}")
    result = _pick_ollama_model(cfg)
    if result is not None:
        return result
    return None

def init_config() -> Config:
    if not _detect_first_run():
        return load_config()
    cfg = Config()
    providers = ["Ollama", "DeepSeek"]
    descs = ["本地或远程部署", "云端 API"]
    choice = select(providers, f"{CYAN}选择 Provider:{RESET}", descs)
    if choice == -1:
        return init_config()
    if choice == 0:
        deploy_opts = ["在本地部署", "已在其他设备部署"]
        deploy_descs = ["本机运行 Ollama", "连接远程服务器"]
        d_choice = select(deploy_opts, f"{CYAN}部署方式:{RESET}", deploy_descs)
        if d_choice == -1:
            return init_config()
        if d_choice == 1:
            return _setup_ollama_remote(cfg)
        result = _setup_ollama_local(cfg)
        if result is not None:
            return result
        return init_config()
    cfg.provider = "deepseek"
    cfg.base_url = "https://api.deepseek.com"
    key = input(f"  {CYAN}DeepSeek API Key{RESET}: ").strip()
    if not key:
        print(f"  {RED}API Key 不能为空{RESET}")
        return init_config()
    cfg.api_key = key
    models = ["deepseek-v4-pro", "deepseek-v4-flash"]
    model_descs = ["旗舰模型", "轻量模型"]
    model_idx = select(models, f"{CYAN}选择模型:{RESET}", model_descs)
    if model_idx == -1:
        return init_config()
    cfg.model = models[model_idx]
    save_config(cfg)
    print(f"  {GREEN}✓{RESET} provider=deepseek model={cfg.model}")
    return cfg