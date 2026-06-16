"""Tests for OutputCompressor."""

import pytest
from pathlib import Path
from agent_token_guard.compressor import OutputCompressor, _OUTPUT_POLICY, _READ_POLICY


@pytest.fixture
def compressor(tmp_path):
    return OutputCompressor(root=tmp_path)


def test_write_policies_creates_files(tmp_path):
    c = OutputCompressor(root=tmp_path)
    c.write_policies()
    assert (tmp_path / ".agent-token-guard" / "rules" / "output-policy.md").exists()
    assert (tmp_path / ".agent-token-guard" / "rules" / "read-policy.md").exists()


def test_output_policy_content(tmp_path):
    c = OutputCompressor(root=tmp_path)
    c.write_policies()
    text = (tmp_path / ".agent-token-guard" / "rules" / "output-policy.md").read_text()
    assert "Answer first" in text
    assert "node_modules" in text


def test_compress_reduces_repeated_lines(compressor):
    repeated = ("INFO: processing item\n" * 20) + "Done.\n"
    compressed, stats = compressor.compress(repeated)
    assert stats["compressed_chars"] < stats["original_chars"]
    assert "repeated" in compressed


def test_compress_trims_python_traceback(compressor):
    trace = (
        "Traceback (most recent call last):\n"
        + "  File 'a.py', line 1, in <module>\n" * 15
        + "ValueError: bad input\n"
    )
    compressed, stats = compressor.compress(trace)
    assert "omitted" in compressed
    assert stats["compressed_chars"] < stats["original_chars"]


def test_compress_stats_keys(compressor):
    text = "hello world\n" * 10
    _, stats = compressor.compress(text)
    for key in ("original_chars", "compressed_chars", "original_tokens", "compressed_tokens", "savings_pct"):
        assert key in stats


def test_compress_short_text_unchanged(compressor):
    text = "One line of text.\n"
    compressed, stats = compressor.compress(text)
    assert compressed.strip() == text.strip()


def test_compress_file(tmp_path):
    c = OutputCompressor(root=tmp_path)
    f = tmp_path / "output.txt"
    f.write_text("WARNING: disk full\n" * 50)
    compressed, stats = c.compress_file(f)
    assert stats["savings_pct"] > 0


def test_normalize_whitespace(compressor):
    text = "line1\n\n\n\n\n\nline2\n"
    compressed, _ = compressor.compress(text)
    assert "\n\n\n\n" not in compressed
