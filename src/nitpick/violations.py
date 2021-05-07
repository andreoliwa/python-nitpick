"""Violation codes.

Name inspired by `flake8's violations <https://flake8.pycqa.org/en/latest/user/error-codes.html>`_.
"""
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Optional

import click

from nitpick.constants import CONFIG_FILES, FLAKE8_PREFIX, READ_THE_DOCS_URL

if TYPE_CHECKING:
    from nitpick.plugins.info import FileInfo


@dataclass(frozen=True)
class Fuss:
    """Nitpick makes a fuss when configuration doesn't match.

    Fields inspired on :py:class:`SyntaxError` and `pyflakes.messages.Message
    <https://github.com/PyCQA/pyflakes/blob/master/pyflakes/messages.py#L6>`_.
    """

    fixed: bool
    filename: str
    code: int
    message: str
    suggestion: str = ""
    lineno: int = 1

    @property
    def colored_suggestion(self) -> str:
        """Suggestion with color."""
        return click.style(f"\n{self.suggestion.rstrip()}", fg="green") if self.suggestion else ""

    @property
    def pretty(self) -> str:
        """Message to be used on the CLI."""
        filename_plus_line = f"{self.filename}:{self.lineno}: " if self.filename.strip() else ""
        return f"{filename_plus_line}{FLAKE8_PREFIX}{self.code:03}" f" {self.message.rstrip()}{self.colored_suggestion}"

    def __lt__(self, other: "Fuss") -> bool:
        """Sort Fuss instances."""
        return (
            self.filename < other.filename
            and self.code < other.code
            and self.message < other.message
            and self.suggestion < other.suggestion
            and self.lineno < other.lineno
        )


class ViolationEnum(Enum):
    """Base enum with violation codes and messages."""

    def __init__(self, code: int, message: str = "", add_to_base=False) -> None:
        self.code = code
        self.message = message
        self.add_code = add_to_base


class StyleViolations(ViolationEnum):
    """Style violations."""

    INVALID_DATA_TOOL_NITPICK = (1, " has an incorrect style. Invalid data in [{section}]:")
    INVALID_TOML = (1, " has an incorrect style. Invalid TOML{exception}")
    INVALID_CONFIG = (1, " has an incorrect style. Invalid config:")


class ProjectViolations(ViolationEnum):
    """Project initialization violations."""

    NO_ROOT_DIR = (
        101,
        "No root directory detected."
        f" Create a configuration file ({', '.join(CONFIG_FILES)}) manually, or run 'nitpick init'."
        f" See {READ_THE_DOCS_URL}configuration.html",
    )
    NO_PYTHON_FILE = (102, "No Python file was found on the root dir and subdir of {root!r}")
    MISSING_FILE = (103, " should exist{extra}")
    FILE_SHOULD_BE_DELETED = (104, " should be deleted{extra}")

    MINIMUM_VERSION = (
        203,
        "The style file you're using requires {project}>={expected} (you have {actual}). Please upgrade",
    )


class SharedViolations(ViolationEnum):
    """Shared violations used by all plugins."""

    CREATE_FILE = (1, " was not found", True)
    CREATE_FILE_WITH_SUGGESTION = (1, " was not found. Create it with this content:", True)
    DELETE_FILE = (2, " should be deleted", True)
    MISSING_VALUES = (8, "{prefix} has missing values:", True)
    DIFFERENT_VALUES = (9, "{prefix} has different values. Use this:", True)


# TODO: the Reporter class should track a global list of codes with __new__(),
#  to be used by the `nitpick violations` CLI command
class Reporter:  # pylint: disable=too-few-public-methods
    """Error reporter."""

    manual: int = 0
    fixed: int = 0

    def __init__(self, info: "FileInfo" = None, violation_base_code: int = 0) -> None:
        self.info: Optional["FileInfo"] = info
        self.violation_base_code = violation_base_code

    def make_fuss(self, violation: ViolationEnum, suggestion: str = "", fixed=False, **kwargs) -> Fuss:
        """Make a fuss."""
        if kwargs:
            formatted = violation.message.format(**kwargs)
        else:
            formatted = violation.message
        base = self.violation_base_code if violation.add_code else 0
        Reporter.increment(fixed)
        # Remove right whitespace from suggestion (new lines, spaces, etc.)
        return Fuss(
            fixed, self.info.path_from_root if self.info else "", base + violation.code, formatted, suggestion.rstrip()
        )

    @classmethod
    def reset(cls):
        """Reset the counters."""
        cls.manual = cls.fixed = 0

    @classmethod
    def increment(cls, fixed=False):
        """Increment the fixed ou manual count."""
        if fixed:
            cls.fixed += 1
        else:
            cls.manual += 1

    @classmethod
    def get_counts(cls) -> str:
        """String representation with error counts and emojis."""
        parts = []
        if cls.fixed:
            parts.append(f"✅ {cls.fixed} fixed")
        if cls.manual:
            parts.append(f"❌ {cls.manual} to change manually")
        if not parts:
            return "No violations found. ✨ 🍰 ✨"
        return f"Violations: {', '.join(parts)}."
