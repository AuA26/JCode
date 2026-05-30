from __future__ import annotations

SKY = "\033[38;2;0;180;255m"
DEEP = "\033[38;2;20;60;180m"
BOLD = "\033[1m"
RESET = "\033[0m"

LOGO = [
    "     ██╗ ██████╗ ██████╗ ██████╗ ███████╗",
    "     ██║██╔════╝██╔═══██╗██╔══██╗██╔════╝",
    "   ██║██║     ██║   ██║██║  ██║█████╗  ",
    "   ██║██║     ██║   ██║██║  ██║██╔══╝  ",
    "╚█████╔╝╚██████╗╚██████╔╝██████╔╝███████╗",
    " ╚════╝  ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝",
]

LOGO_WIDTH = max(len(line.rstrip()) for line in LOGO)  # 47

INFO_LINES = [
    ("Coding Agent ", "{ver}"),
    ("github.com/AuA26/JCode", ""),
]

INFO_WIDTH = max(
    len(line[0]) + len(line[1]) if line[1] else len(line[0])
    for line in INFO_LINES
)


def _text_width(s: str) -> int:
    return len(s.replace(SKY, "").replace(DEEP, "").replace(BOLD, "").replace(RESET, ""))


def render(version: str) -> str:
    ver_text = f"v{version}"
    w = max(LOGO_WIDTH, INFO_WIDTH + len(ver_text)) + 6
    border_top = f"{DEEP}╔{'═' * w}╗{RESET}"
    border_bot = f"{DEEP}╚{'═' * w}╝{RESET}"
    mid = f"{DEEP}║{RESET}"
    lines = [border_top, f"{mid}{' ' * w}{mid}"]

    for logo_line in LOGO:
        stripped = logo_line.rstrip()
        pad_l = (w - len(stripped)) // 2
        pad_r = w - len(stripped) - pad_l
        colored = f"{SKY}{BOLD}{stripped}{RESET}"
        lines.append(f"{mid}{' ' * pad_l}{colored}{' ' * pad_r}{mid}")

    lines.append(f"{mid}{' ' * w}{mid}")

    tag = f"{SKY}{BOLD}Coding Agent{RESET}  {DEEP}{ver_text}{RESET}"
    tag_w = _text_width(tag)
    lines.append(f"{mid}  {tag}{' ' * (w - 2 - tag_w)}{mid}")

    url = f"{DEEP}github.com/AuA26/JCode{RESET}"
    url_w = _text_width(url)
    lines.append(f"{mid}  {url}{' ' * (w - 2 - url_w)}{mid}")

    lines.append(f"{mid}{' ' * w}{mid}")
    lines.append(border_bot)
    return "\n".join(lines)
