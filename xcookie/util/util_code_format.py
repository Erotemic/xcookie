# util_code_format.py
r"""
Utilities for formatting Python code stored as text, with a pluggable backend
architecture.

TODO:
    - [ ] Read in the project pyproject.toml and use whatever that ruff config is by default.

This module is designed for situations where you have a block of code as a
string (e.g. generated code, code extracted from docs, editor integrations)
and you want to run a formatter on it without writing a real source file.

Backends:
    - Ruff (default): Invokes the `ruff` CLI and formats via stdin.
    - Black: Uses the Python `black` library if installed.

Default behavior:
    The default backend is Ruff with `quote-style = "single"`.

Example:
    >>> # xdoctest: +REQUIRES(module:ruff)
    >>> from xcookie.util.util_code_format import format_code, make_backend, RuffFormatConfig
    >>> text = 'print("hello")\n'
    >>> out = format_code(text)  # default backend: ruff w/ single quotes
    >>> "print('hello')" in out
    True
    >>> backend = make_backend(
    ...     "ruff",
    ...     ruff_config=RuffFormatConfig(
    ...         quote_style="single",
    ...         line_length=88,
    ...     ),
    ... )
    >>> out2 = format_code('x = {"a": 1, "b": 2}\n', backend=backend)
    >>> out2.endswith("\n")
    True

    Black usage (optional; requires `pip install black`):

    >>> # xdoctest: +REQUIRES(module:black)
    >>> out3 = format_code('x=  1\n', backend="black")  # xdoctest: +SKIP
    >>> isinstance(out3, str)  # xdoctest: +SKIP
    True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol, Union, Literal
import os
import subprocess
import tempfile


# -------------------------
# Exceptions
# -------------------------


class CodeFormatError(RuntimeError):
    """Raised when a formatter backend fails."""


# -------------------------
# Backend protocol
# -------------------------


class FormatterBackend(Protocol):
    """Minimal protocol for formatter backends."""

    name: str

    def format_text(self, text: str, *, filename: str = "snippet.py") -> str:
        """Format a code string and return the formatted string."""
        ...


# -------------------------
# Ruff backend
# -------------------------


@dataclass(frozen=True)
class RuffFormatConfig:
    """
    Configuration for the Ruff backend.

    Notes:
        Ruff's `line-length` is a top-level setting under `[tool.ruff]`, not
        under `[tool.ruff.format]` for the Ruff versions that error on unknown
        fields (as seen in the user's traceback). Some docstring formatting
        knobs live under `[tool.ruff.format]` (e.g. `docstring-code-line-length`).

    Attributes:
        quote_style: Maps to `[tool.ruff.format].quote-style`.
        indent_style: Maps to `[tool.ruff.format].indent-style`.
        skip_magic_trailing_comma: Maps to `[tool.ruff.format].skip-magic-trailing-comma`.
        preview: Maps to `[tool.ruff.format].preview`.
        docstring_code_format: Maps to `[tool.ruff.format].docstring-code-format`.
        docstring_code_line_length: Maps to `[tool.ruff.format].docstring-code-line-length`.
        line_length: Maps to `[tool.ruff].line-length` (top-level).
        extra_format: Extra keys to add to `[tool.ruff.format]`.
        extra_tool: Extra keys to add to `[tool.ruff]`.
    """

    # [tool.ruff.format]
    quote_style: Literal["single", "double", "preserve"] = "single"
    indent_style: Optional[Literal["space", "tab"]] = None
    skip_magic_trailing_comma: Optional[bool] = None
    preview: Optional[bool] = None
    docstring_code_format: Optional[bool] = None
    docstring_code_line_length: Optional[int] = None

    # [tool.ruff]
    line_length: Optional[int] = 80

    # Escape hatches
    extra_format: Mapping[str, Any] = field(default_factory=dict)
    extra_tool: Mapping[str, Any] = field(default_factory=dict)


def _toml_quote(s: str) -> str:
    """Minimal TOML string quoting (sufficient for our use-case)."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _toml_value(v: Any) -> str:
    """Convert a Python scalar into a TOML literal."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return _toml_quote(v)
    if v is None:
        raise ValueError("None is not a valid TOML value here")
    raise TypeError(f"Unsupported TOML value type: {type(v)!r}")


def _toml_table(table: Mapping[str, Any], *, header: str) -> str:
    """Render a TOML table section."""
    lines = [f"[{header}]"]
    for k, v in table.items():
        if v is None:
            continue
        lines.append(f"{k} = {_toml_value(v)}")
    return "\n".join(lines) + "\n"


def _ruff_config_to_toml(cfg: RuffFormatConfig) -> str:
    """
    Build a minimal TOML config string for Ruff.

    We intentionally place `line-length` under `[tool.ruff]` (top-level) to
    avoid versions of Ruff that reject `line-length` under `[tool.ruff.format]`.
    """
    # Top-level [tool.ruff]
    tool_table: Dict[str, Any] = dict(cfg.extra_tool)
    if cfg.line_length is not None:
        tool_table["line-length"] = cfg.line_length
    tool_table = {k: v for k, v in tool_table.items() if v is not None}

    # [tool.ruff.format]
    format_table: Dict[str, Any] = {
        "quote-style": cfg.quote_style,
        "indent-style": cfg.indent_style,
        "skip-magic-trailing-comma": cfg.skip_magic_trailing_comma,
        "preview": cfg.preview,
        "docstring-code-format": cfg.docstring_code_format,
        "docstring-code-line-length": cfg.docstring_code_line_length,
    }
    format_table.update(dict(cfg.extra_format))
    format_table = {k: v for k, v in format_table.items() if v is not None}

    toml = ""
    if tool_table:
        toml += _toml_table(tool_table, header="tool.ruff")
    toml += _toml_table(format_table, header="tool.ruff.format")
    return toml


@dataclass
class RuffFormatterBackend:
    """
    Ruff formatter backend.

    Requires:
        - `ruff` to be available on PATH (or specify `ruff_executable`).
    """

    config: RuffFormatConfig = field(default_factory=RuffFormatConfig)
    ruff_executable: str = "ruff"
    name: str = "ruff"

    def format_text(self, text: str, *, filename: str = "snippet.py") -> str:
        """
        Format code using `ruff format` via stdin.

        Args:
            text: Code to format.
            filename: Virtual filename used by Ruff for stdin input.

        Returns:
            The formatted code (stdout from `ruff format`).

        Raises:
            CodeFormatError: If Ruff fails or returns a non-zero exit code.
        """
        toml = _ruff_config_to_toml(self.config)

        with tempfile.TemporaryDirectory(prefix="util_code_format_") as d:
            cfg_path = os.path.join(d, "pyproject.toml")
            with open(cfg_path, "w", encoding="utf-8") as f:
                f.write(toml)

            cmd = [
                self.ruff_executable,
                "format",
                "-",  # stdin
                "--stdin-filename",
                filename,
                "--config",
                cfg_path,
            ]

            p = subprocess.run(
                cmd,
                input=text,
                text=True,
                capture_output=True,
            )

        if p.returncode != 0:
            msg = "\n".join(
                [
                    "Ruff formatting failed.",
                    f"Command: {' '.join(cmd)}",
                    f"Return code: {p.returncode}",
                    "---- stderr ----",
                    (p.stderr or "").strip(),
                    "---- stdout ----",
                    (p.stdout or "").strip(),
                ]
            ).strip()
            raise CodeFormatError(msg)

        return p.stdout


# -------------------------
# Black backend
# -------------------------


@dataclass(frozen=True)
class BlackConfig:
    """
    Configuration for the Black backend.

    Attributes:
        line_length: Passed to `black.Mode(line_length=...)` when not None.
        string_normalization: Passed to `black.Mode(string_normalization=...)`.
        is_pyi: Passed to `black.Mode(is_pyi=...)`.
        mode_kwargs: Extra kwargs forwarded to `black.Mode(...)`.
    """

    line_length: Optional[int] = None
    string_normalization: bool = True
    is_pyi: bool = False
    mode_kwargs: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class BlackFormatterBackend:
    """Black formatter backend (requires `black` import)."""

    config: BlackConfig = field(default_factory=BlackConfig)
    name: str = "black"

    def format_text(self, text: str, *, filename: str = "snippet.py") -> str:
        """
        Format code using Black's Python API.

        Args:
            text: Code to format.
            filename: Currently unused (kept for protocol compatibility).

        Returns:
            The formatted code.

        Raises:
            CodeFormatError: If Black is not installed or formatting fails.
        """
        try:
            import black  # type: ignore
        except Exception as e:
            raise CodeFormatError(
                "Black backend requested, but `black` could not be imported. "
                "Install it (e.g. `pip install black`)."
            ) from e

        try:
            mode_kwargs = dict(self.config.mode_kwargs)
            if self.config.line_length is not None:
                mode_kwargs["line_length"] = self.config.line_length

            mode = black.Mode(
                string_normalization=self.config.string_normalization,
                is_pyi=self.config.is_pyi,
                **mode_kwargs,
            )
            return black.format_str(text, mode=mode)
        except Exception as e:
            raise CodeFormatError(f"Black formatting failed: {e}") from e


# -------------------------
# Public API / dispatcher
# -------------------------


BackendName = Literal["ruff", "black"]
Backend = Union[BackendName, FormatterBackend]


def make_backend(
    backend: BackendName = "ruff",
    *,
    ruff_config: Optional[RuffFormatConfig] = None,
    black_config: Optional[BlackConfig] = None,
    ruff_executable: str = "ruff",
) -> FormatterBackend:
    """
    Convenience factory for formatter backends.

    Args:
        backend: Name of the backend.
        ruff_config: Configuration for Ruff (if backend == "ruff").
        black_config: Configuration for Black (if backend == "black").
        ruff_executable: Ruff executable to invoke.

    Returns:
        A backend instance implementing `FormatterBackend`.

    Raises:
        ValueError: If `backend` is unknown.
    """
    if backend == "ruff":
        return RuffFormatterBackend(
            config=ruff_config or RuffFormatConfig(),
            ruff_executable=ruff_executable,
        )
    if backend == "black":
        return BlackFormatterBackend(config=black_config or BlackConfig())
    raise ValueError(f"Unknown backend: {backend!r}")


def format_code(
    text: str,
    *,
    backend: Backend = "ruff",
    filename: str = "snippet.py",
) -> str:
    """
    Format code using the requested backend.

    Args:
        text: Code to format.
        backend: "ruff", "black", or a custom backend implementing
            `FormatterBackend`.
        filename: Virtual filename used by formatters when reading from stdin
            (notably Ruff).

    Returns:
        The formatted code as a string.

    Raises:
        CodeFormatError: If the formatter fails.
    """
    be: FormatterBackend
    if isinstance(backend, str):
        be = make_backend(backend)
    else:
        be = backend
    return be.format_text(text, filename=filename)


if __name__ == "__main__":
    sample = 'import os,sys\n\nx=  1\nprint("hi")\n'
    print("---- input ----")
    print(sample)

    out = format_code(sample)
    print("---- ruff output ----")
    print(out)

    try:
        out2 = format_code(sample, backend="black")
        print("---- black output ----")
        print(out2)
    except CodeFormatError as ex:
        print("Black not available:", ex)
