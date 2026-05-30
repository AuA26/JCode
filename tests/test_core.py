from __future__ import annotations
from pathlib import Path

from main_code.config import Config
from main_code.gate import classify, RouteResult
from main_code.tools import read_file, write_file, run_cmd, list_files, CmdResult
from main_code.verifier import verify, VerifyResult, _check_syntax, _classify_error
from main_code.context import Context


class TestConfig:
    def test_default_config(self):
        cfg = Config()
        assert cfg.provider == ""
        assert not cfg.is_configured

    def test_configured(self):
        cfg = Config(provider="ollama", model="qwen3:8b", base_url="http://localhost:11434/v1")
        assert cfg.is_configured


class TestGate:
    def test_bugfix_keywords(self):
        result = classify("\u4fee\u590d\u767b\u5f55\u9875\u9762\u7684\u62a5\u9519")
        assert result.route == "bugfix"
        assert result.source == "keyword"
        assert result.confidence > 0.7

    def test_codegen_keywords(self):
        result = classify("\u5199\u4e00\u4e2aFastAPI\u7684\u7528\u6237\u6ce8\u518c\u63a5\u53e3")
        assert result.route == "codegen"
        assert result.source == "keyword"

    def test_refactor_keywords(self):
        result = classify("\u91cd\u6784utils.py\u91cc\u7684\u6570\u636e\u5904\u7406\u903b\u8f91")
        assert result.route == "refactor"
        assert result.source == "keyword"

    def test_explain_keywords(self):
        result = classify("\u89e3\u91ca\u4e00\u4e0b\u8fd9\u4e2a\u88c5\u9970\u5668\u662f\u600e\u4e48\u5de5\u4f5c\u7684")
        assert result.route == "explain"

    def test_test_keywords(self):
        result = classify("\u5199\u5355\u5143\u6d4b\u8bd5\u8986\u76d6auth\u6a21\u5757")
        assert result.route == "test"

    def test_empty_input(self):
        result = classify("")
        assert result.route == "chat"

    def test_ambiguous_fallback_chat(self):
        result = classify("\u4f60\u597d")
        assert result.route == "chat"

    def test_route_pipeline(self):
        result = classify("\u4fee\u590dbug")
        assert result.pipeline == ["locator", "generator", "verifier"]

    def test_codegen_pipeline(self):
        result = classify("\u5199\u4e00\u4e2a\u51fd\u6570")
        assert "generator" in result.pipeline


class TestTools:
    def test_read_write_file(self, tmp_path):
        test_file = tmp_path / "test.txt"
        write_file(test_file, "hello world")
        content = read_file(test_file)
        assert content == "hello world"

    def test_read_nonexistent(self):
        try:
            read_file("/nonexistent/path/file.py")
            assert False
        except FileNotFoundError:
            pass

    def test_run_cmd(self):
        result = run_cmd("python -c \"print('ok')\"")
        assert result.ok
        assert "ok" in result.stdout

    def test_run_cmd_timeout(self):
        result = run_cmd("python -c \"import time; time.sleep(10)\"", timeout=1)
        assert not result.ok or result.timed_out

    def test_list_files(self, tmp_path):
        (tmp_path / "a.py").write_text("x=1")
        (tmp_path / "b.py").write_text("y=2")
        (tmp_path / "c.txt").write_text("z=3")
        files = list_files(tmp_path, "*.py")
        assert len(files) == 2


class TestVerifier:
    def test_syntax_ok(self):
        ok, err = _check_syntax("def foo(): return 42")
        assert ok
        assert err == ""

    def test_syntax_error(self):
        ok, err = _check_syntax("def foo(: return 42")
        assert not ok
        assert "SyntaxError" in err or "invalid syntax" in err or "syntax" in err.lower()

    def test_classify_errors(self):
        assert _classify_error("SyntaxError: invalid syntax") == "syntax"
        assert _classify_error("AssertionError: assert 1 == 2") == "assertion"
        assert _classify_error("ModuleNotFoundError: No module named 'xxx'") == "import"

    def test_verify_good_code(self):
        result = verify("def hello(): return 'world'")
        assert result.ok
        assert result.syntax_ok

    def test_verify_bad_code(self):
        result = verify("def hello(: return 'world'")
        assert not result.ok
        assert not result.syntax_ok


class TestContext:
    def test_add_get_messages(self):
        ctx = Context()
        ctx.add_message("user", "hello")
        ctx.add_message("assistant", "hi")
        assert len(ctx.get_history()) == 2

    def test_max_history(self):
        ctx = Context(max_history=3)
        for i in range(5):
            ctx.add_message("user", f"msg{i}")
        assert len(ctx.get_history()) == 3
        assert ctx.get_history()[0]["content"] == "msg2"

    def test_clear(self):
        ctx = Context()
        ctx.add_message("user", "hello")
        ctx.clear()
        assert len(ctx.get_history()) == 0

    def test_estimate_tokens(self):
        ctx = Context()
        tokens = ctx.estimate_tokens("hello world")
        assert tokens > 0
        tokens_cn = ctx.estimate_tokens("\u4f60\u597d\u4e16\u754c")
        assert tokens_cn >= 4

    def test_file_context(self):
        ctx = Context()
        ctx.set_files([Path("a.py"), Path("b.py")])
        ctx.add_file(Path("c.py"))
        assert len(ctx.current_files) == 3
        prompt = ctx.build_context_prompt()
        assert "a.py" in prompt
