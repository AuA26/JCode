from __future__ import annotations
import logging
from pathlib import Path

logging.basicConfig(level=logging.WARNING, format="[%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("jcode")

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion

from main_code.config import init_config, Config
from main_code.gate import classify_multi, RouteResult
from main_code.context import Context
from main_code.llm import chat, classify_steps
from main_code.pipeline import run_pipeline
from main_code.commands import handle_command, COMMAND_DESCRIPTIONS
from main_code.version import get_local_version
from main_code.banner import render


class SlashCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()
        if not text.startswith("/"):
            return
        for cmd, desc in COMMAND_DESCRIPTIONS.items():
            if cmd.startswith(text[1:]):
                yield Completion(cmd, start_position=-len(text) + 1, display_meta=desc)


session = PromptSession("  > ", completer=SlashCompleter())


def main():
    ver = get_local_version()
    print(f"\n{render(ver)}\n")

    cfg = init_config()
    ctx = Context()
    project_dir = Path.cwd()

    print(f"  文件目录: {project_dir}")
    print(f"  模型供应商: {cfg.provider}")
    print(f"  模型: {cfg.model}")
    print(f"  /help 获取帮助\n")

    while True:
        try:
            raw = session.prompt()
            user_input = raw.strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  bye")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            parts = user_input.split(maxsplit=2)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            args2 = parts[2] if len(parts) > 2 else ""
            should_exit, cfg, project_dir = handle_command(cmd, args, args2, cfg, ctx, project_dir)
            if should_exit:
                break
            continue

        routes = classify_multi(user_input, classify_steps, cfg)
        ctx.add_message("user", user_input)
        non_chat = [r for r in routes if r.route != "chat"]
        if not non_chat:
            response = chat(
                messages=[{"role": "user", "content": user_input}],
                cfg=cfg,
                system_prompt="你是 JCode，一个本地模型友好的 AI 编程助手。你可以回答编程问题、解释代码、提供技术建议。用中文回复。"
            )
            print(f"\n{response}\n")
            ctx.add_message("assistant", response)
        else:
            if len(non_chat) > 1:
                print(f"  multi-step: {' → '.join(r.route for r in non_chat)}")
            else:
                route_label = non_chat[0].route
                if non_chat[0].expert:
                    route_label += f"+{non_chat[0].expert}"
                print(f"  route: {route_label}")
            response = run_pipeline(user_input, non_chat, project_dir, cfg, ctx)
            ctx.add_message("assistant", response)

        print()


if __name__ == "__main__":
    main()
