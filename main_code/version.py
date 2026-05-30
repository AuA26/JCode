import httpx
import json
from pathlib import Path

LOCAL_VERSION_FILE = Path(__file__).parent / "version.json"

def get_local_version() -> str:
    try:
        with open(LOCAL_VERSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("version", "0.0.0")
    except (FileNotFoundError, json.JSONDecodeError):
        return "0.0.0"


def get_remote_version(url: str = "") -> str:
    if not url:
        return ""
    try:
        resp = httpx.get(url, timeout=5)
        data = resp.json()
        return data.get("version", "")
    except Exception:
        return ""


def check_version(version_url: str = "") -> str:
    local = get_local_version()
    if not version_url:
        return "offline"
    remote = get_remote_version(version_url)
    if not remote:
        return "offline"
    if remote > local:
        print(f"  本地版本: {local}")
        print(f"  最新版本: {remote}")
        print("  请运行 pip install jcode --upgrade 更新")
        return "update"
    else:
        print(f"  当前版本: {local} (已是最新)")
        return "latest"