import httpx

GITHUB_URL = "https://raw.githubusercontent.com/AuA26/JCode/main/main_code/version.json"
DOMESTIC_URL = "" 


def test_github() -> bool:
    try:
        resp = httpx.head("https://github.com", timeout=5)
        return resp.status_code < 400
    except Exception:
        return False


def get_version_url() -> str:
    if test_github():
        return GITHUB_URL
    elif DOMESTIC_URL:
        return DOMESTIC_URL
    return ""
