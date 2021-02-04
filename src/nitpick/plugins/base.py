"""Base class for file checkers."""
import abc
from functools import lru_cache
from pathlib import Path
from typing import Iterator, Optional, Set, Type

import jmespath
from autorepr import autotext
from loguru import logger
from marshmallow import Schema

from nitpick.exceptions import NitpickError
from nitpick.formats import Comparison
from nitpick.generic import search_dict
from nitpick.plugins.data import FileData
from nitpick.typedefs import JsonDict, mypy_property
from nitpick.violations import Reporter, SharedViolations, ViolationEnum


class NitpickPlugin(metaclass=abc.ABCMeta):
    """Base class for file checkers."""

    __str__, __unicode__ = autotext("{self.data.path_from_root} ({self.__class__.__name__})")

    file_name = ""  # TODO: remove file_name attribute after fixing dynamic/fixed schema loading
    violation_base_code: int = 0
    error_codes: Optional[Type[ViolationEnum]] = None

    #: Nested validation field for this file, to be applied in runtime when the validation schema is rebuilt.
    #: Useful when you have a strict configuration for a file type (e.g. :py:class:`nitpick.plugins.json.JSONPlugin`).
    validation_schema: Optional[Schema] = None

    #: Which ``identify`` tags this :py:class:`nitpick.plugins.base.NitpickPlugin` child recognises.
    identify_tags: Set[str] = set()

    skip_empty_suggestion = False

    def __init__(self, data: FileData) -> None:
        self.data = data
        self.file_name = data.path_from_root
        self.reporter = Reporter(data, self.violation_base_code)

        self.file_path: Path = self.data.project.root / self.file_name

        # Configuration for this file as a TOML dict, taken from the style file.
        self.file_dict: JsonDict = {}

    @mypy_property
    @lru_cache()
    def nitpick_file_dict(self) -> JsonDict:
        """Nitpick configuration for this file as a TOML dict, taken from the style file."""
        return search_dict(f'files."{self.file_name}"', self.data.project.nitpick_section, {})

    @classmethod
    def get_compiled_jmespath_file_names(cls):
        """Return a compiled JMESPath expression for file names, using the class name as part of the key."""
        return jmespath.compile(f"nitpick.{cls.__name__}.file_names")

    def entry_point(self, config: JsonDict) -> Iterator[NitpickError]:
        """Entry point of the Nitpick plugin."""
        self.file_dict = config or {}

        config_data_exists = bool(self.file_dict or self.nitpick_file_dict)
        should_exist: bool = self.data.project.nitpick_files_section.get(self.file_name, True)
        file_exists = self.file_path.exists()

        if config_data_exists and not file_exists:
            logger.info(f"{self}: Suggest initial contents for {self.file_name}")
            suggestion = self.suggest_initial_contents()
            if not suggestion and self.skip_empty_suggestion:
                return
            if suggestion:
                yield self.reporter.make_error(SharedViolations.CreateFileWithSuggestion, suggestion)
            else:
                yield self.reporter.make_error(SharedViolations.CreateFile)

        elif not should_exist and file_exists:
            logger.info(f"{self}: File {self.file_name} exists when it should not")
            # Only display this message if the style is valid.
            yield self.reporter.make_error(SharedViolations.DeleteFile)
        elif file_exists and config_data_exists:
            logger.info(f"{self}: Enforcing rules")
            yield from self.enforce_rules()

    @abc.abstractmethod
    def enforce_rules(self) -> Iterator[NitpickError]:
        """Enforce rules for this file. It should be overridden by inherited classes if needed."""

    @abc.abstractmethod
    def suggest_initial_contents(self) -> str:
        """Suggest the initial content for this missing file."""

    def warn_missing_different(self, comparison: Comparison, prefix: str = "") -> Iterator[NitpickError]:
        """Warn about missing and different keys."""
        # pylint: disable=not-callable
        if comparison.missing_format:
            yield self.reporter.make_error(
                SharedViolations.MissingValues, comparison.missing_format.reformatted, prefix=prefix
            )
        if comparison.diff_format:
            yield self.reporter.make_error(
                SharedViolations.DifferentValues, comparison.diff_format.reformatted, prefix=prefix
            )
