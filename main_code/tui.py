from __future__ import annotations
import sys
import os


def _raw_key() -> str:
    if sys.platform == "win32":
        import msvcrt
        ch = msvcrt.getch()
        if ch == b"\xe0" or ch == b"\x00":
            ch2 = msvcrt.getch()
            return {b"H": "UP", b"P": "DOWN", b"K": "LEFT", b"M": "RIGHT"}.get(ch2, "")
        if ch == b"\x1b":
            return "ESC"
        if ch == b"\r":
            return "ENTER"
        if ch == b"\x03":
            raise KeyboardInterrupt
        if ch == b"\t":
            return "TAB"
        return ch.decode("utf-8", errors="replace")
    else:
        import tty
        import termios
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = os.read(fd, 3)
            if ch == b"\x1b":
                ch2 = os.read(fd, 2)
                if ch2 == b"[A":
                    return "UP"
                if ch2 == b"[B":
                    return "DOWN"
                if ch2 == b"[C":
                    return "RIGHT"
                if ch2 == b"[D":
                    return "LEFT"
                return "ESC"
            if ch in (b"\r", b"\n"):
                return "ENTER"
            return ch.decode("utf-8", errors="replace")
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def select(options: list[str], prompt: str = "", descriptions: list[str] | None = None) -> int:
    n = len(options)
    idx = 0
    descs = descriptions or [""] * n

    def _draw():
        sys.stdout.write(prompt + "\n\n")
        for i, opt in enumerate(options):
            prefix = "  \u25b6" if i == idx else "   "
            d = f"  ({descs[i]})" if descs[i] else ""
            if i == idx:
                sys.stdout.write(f"\033[7m{prefix} {opt}{d}\033[0m\n")
            else:
                sys.stdout.write(f"{prefix} {opt}{d}\n")
        sys.stdout.write("\n  ESC = back\n")

    _draw()
    while True:
        key = _raw_key()
        if key == "UP":
            idx = (idx - 1) % n
        elif key == "DOWN":
            idx = (idx + 1) % n
        elif key == "ENTER":
            for _ in range(n + 4):
                sys.stdout.write("\033[1A\033[2K")
            return idx
        elif key == "ESC":
            for _ in range(n + 4):
                sys.stdout.write("\033[1A\033[2K")
            return -1
        else:
            continue
        for _ in range(n + 4):
            sys.stdout.write("\033[1A\033[2K")
        _draw()


def input_cmd(prompt: str, completions: list[str]) -> str:
    raw = input(prompt)
    if not raw.startswith("/"):
        return raw
    cmd = raw.strip().lower()
    if cmd in ("/" + c for c in completions):
        return cmd
    prefix = cmd[1:]
    matches = [c for c in completions if c.startswith(prefix)]
    if not matches:
        print(f"  unknown: {cmd}  /help for help")
        return ""
    if len(matches) == 1:
        return "/" + matches[0]
    sys.stdout.write(f"  commands: {'  '.join(matches)}\n")
    idx = 0
    sys.stdout.write(f"\r  \033[7m/{matches[0]}\033[0m  ")
    sys.stdout.flush()
    while True:
        key = _raw_key()
        if key == "RIGHT":
            idx = (idx + 1) % len(matches)
            sys.stdout.write(f"\r  \033[7m/{matches[idx]}\033[0m  ")
            sys.stdout.flush()
        elif key == "LEFT":
            idx = (idx - 1) % len(matches)
            sys.stdout.write(f"\r  \033[7m/{matches[idx]}\033[0m  ")
            sys.stdout.flush()
        elif key == "ENTER":
            result = "/" + matches[idx]
            sys.stdout.write(f"\r  {result}\033[K\n")
            sys.stdout.flush()
            return result
        elif key == "ESC":
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()
            return ""
