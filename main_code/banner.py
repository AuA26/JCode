from __future__ import annotations

SKY = "\033[38;2;0;180;255m"
DEEP = "\033[38;2;20;60;180m"
BOLD = "\033[1m"
RESET = "\033[0m"

LOGO = [
    "     ██╗ ██████╗ ██████╗ ██████╗ ███████╗",
    "     ██║██╔════╝██╔═══██╗██╔══██╗██╔════╝",
    "     ██║██║     ██║   ██║██║  ██║█████╗  ",
    "██   ██║██║     ██║   ██║██║  ██║██╔══╝  ",
    "╚█████╔╝╚██████╗╚██████╔╝██████╔╝███████╗",
    " ╚════╝  ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝",
]


def _visible(s: str) -> int:
    return len(s.replace(SKY, "").replace(DEEP, "").replace(BOLD, "").replace(RESET, ""))


def render(version: str) -> str:
    w = 50
    border_top = f"{DEEP}╔{'═' * w}╗{RESET}"
    border_bot = f"{DEEP}╚{'═' * w}╝{RESET}"
    mid = f"{DEEP}║{RESET}"
    pad = " " * ((w - 48) // 2)

    lines = [border_top]
    lines.append(f"{mid}{' ' * w}{mid}")

    for logo_line in LOGO:
        lines.append(f"{mid}{pad}{SKY}{BOLD}{logo_line}{RESET}{pad}{mid}")

    lines.append(f"{mid}{' ' * w}{mid}")

    tag = f"{SKY}{BOLD}Coding Agent{RESET}"
    ver = f"{DEEP}v{version}{RESET}"
    vis_tag = _visible(tag + ver)
    gap = " " * (w - 2 - vis_tag)
    lines.append(f"{mid} {tag}  {ver}{gap}{mid}")

    url = f"{DEEP}github.com/AuA26/JCode{RESET}"
    vis_url = _visible(url)
    lines.append(f"{mid}  {url}{' ' * (w - 2 - vis_url)}{mid}")

    lines.append(f"{mid}{' ' * w}{mid}")
    lines.append(border_bot)
    return "\n".join(lines)
