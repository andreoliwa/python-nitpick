"""Enforce config on `pyproject.toml <https://github.com/python-poetry/poetry/blob/master/docs/docs/pyproject.md>`_."""
from collections import OrderedDict
from typing import Iterator, Optional, Type

from tomlkit import dumps, parse
from tomlkit.toml_document import TOMLDocument

from nitpick.constants import PYPROJECT_TOML
from nitpick.core import Nitpick
from nitpick.generic import singleton
from nitpick.plugins import hookimpl
from nitpick.plugins.base import NitpickPlugin
from nitpick.plugins.data import FileData
from nitpick.violations import Fuss, SharedViolations, ViolationCounter


def change_toml(document: TOMLDocument, dictionary):
    """Traverse a TOML document recursively and change values, keeping its formatting and comments."""
    for key, value in dictionary.items():
        if isinstance(value, (dict, OrderedDict)):
            if key in document:
                change_toml(document[key], value)
            else:
                document.add(key, value)
        else:
            document[key] = value


class PyProjectTomlPlugin(NitpickPlugin):
    """Enforce config on `pyproject.toml <https://github.com/python-poetry/poetry/blob/master/docs/docs/pyproject.md>`_.

    See also `PEP 518 <https://www.python.org/dev/peps/pep-0518/>`_.

    Example: :ref:`the Python 3.7 default <default-python-3-7>`.
    There are many other examples in :ref:`defaults`.
    """

    filename = PYPROJECT_TOML
    violation_base_code = 310

    def enforce_rules(self) -> Iterator[Fuss]:
        """Enforce rules for missing key/value pairs in pyproject.toml."""
        file = Nitpick.singleton().project.pyproject_toml
        if not file:
            return

        comparison = file.compare_with_flatten(self.file_dict)
        if not comparison.has_changes:
            return

        if self.apply:
            document = parse(file.as_string)
        if comparison.diff:
            if self.apply:
                change_toml(document, comparison.diff.as_data)
            yield self.reporter.make_fuss(SharedViolations.DifferentValues, comparison.diff.reformatted, prefix="")
        if comparison.missing:
            if self.apply:
                change_toml(document, comparison.missing.as_data)
            yield self.reporter.make_fuss(SharedViolations.MissingValues, comparison.missing.reformatted, prefix="")
        if self.apply:
            self.file_path.write_text(dumps(document))

    def suggest_initial_contents(self) -> str:
        """Suggest the initial content for this missing file."""
        return ""


@hookimpl
def plugin_class() -> Type["NitpickPlugin"]:
    """You should return your plugin class here."""
    return PyProjectTomlPlugin


@hookimpl
def can_handle(data: FileData) -> Optional["NitpickPlugin"]:
    """Handle pyproject.toml file."""
    if data.path_from_root == PYPROJECT_TOML:
        return PyProjectTomlPlugin(data)
    return None
