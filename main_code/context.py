from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Context:
    history: list[dict] = field(default_factory=list)
    current_files: list[Path] = field(default_factory=list)
    max_history: int = 20

    def add_message(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def get_history(self, n: int | None = None) -> list[dict]:
        if n is None:
            return list(self.history)
        return self.history[-n:]

    def set_files(self, files: list[Path]) -> None:
        self.current_files = [Path(f) for f in files]

    def add_file(self, filepath: Path) -> None:
        if filepath not in self.current_files:
            self.current_files.append(filepath)

    def estimate_tokens(self, text: str) -> int:
        chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other = len(text) - chinese
        return chinese + (other // 4) + 1

    def clear(self) -> None:
        self.history = []

    def build_context_prompt(self) -> str:
        if not self.current_files:
            return ""
        lines = ["\n--- files ---"]
        for f in self.current_files[:10]:
            lines.append(f"  {f}")
        return "\n".join(lines)
