"""Write documentation files content from Python classes.

Run on the dev machine with "invoke doc", and commit on GitHub.

The ``include`` directive is not working on Read the Docs.
It doesn't recognise the "styles" dir anywhere (on the root, under "docs", under "_static"...).
Not even changing ``html_static_path`` on ``conf.py`` worked.
"""
import sys
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from pprint import pprint
from subprocess import check_output  # nosec
from textwrap import dedent, indent
from typing import List, Set, Tuple, Union

import click
from slugify import slugify
from sortedcontainers import SortedDict

from nitpick import PROJECT_NAME, __version__
from nitpick.constants import (
    CONFIG_FILES,
    EDITOR_CONFIG,
    PACKAGE_JSON,
    PRE_COMMIT_CONFIG_YAML,
    PROJECT_OWNER,
    PYLINTRC,
    PYPROJECT_TOML,
    READ_THE_DOCS_URL,
    SETUP_CFG,
)
from nitpick.core import Nitpick
from nitpick.style.fetchers.github import GitHubURL

RST_DIVIDER_FROM_HERE = ".. auto-generated-from-here"
RST_DIVIDER_START = ".. auto-generated-start-{}"
RST_DIVIDER_END = ".. auto-generated-end-{}"

MD_DIVIDER_START = "<!-- auto-generated-start-{} -->"
MD_DIVIDER_END = "<!-- auto-generated-end-{} -->"

DOCS_DIR: Path = Path(__file__).parent.absolute()
STYLES_DIR: Path = DOCS_DIR.parent / "styles"

STYLE_MAPPING = SortedDict(
    {
        "absent-files.toml": "Absent files",
        "black.toml": "black_",
        "editorconfig.toml": "EditorConfig_",
        "flake8.toml": "flake8_",
        "ipython.toml": "IPython_",
        "isort.toml": "isort_",
        "mypy.toml": "mypy_",
        "package-json.toml": "package.json_",
        "poetry.toml": "Poetry_",
        "pre-commit/bash.toml": "Bash_",
        "pre-commit/commitlint.toml": "commitlint_",
        "pre-commit/general.toml": "pre-commit_ (hooks)",
        "pre-commit/main.toml": "pre-commit_ (main)",
        "pre-commit/python.toml": "pre-commit_ (Python hooks)",
        "pylint.toml": "Pylint_",
        "python36.toml": "Python 3.6",
        "python37.toml": "Python 3.7",
        "python38.toml": "Python 3.8",
        "python39.toml": "Python 3.9",
        "tox.toml": "tox_",
    }
)
CLI_MAPPING = [
    ("", "Main options", ""),
    (
        "fix",
        "Modify files directly",
        """
        At the end of execution, this command displays:

        - the number of fixed violations;
        - the number of violations that have to be changed manually.
        """,
    ),
    ("check", "Don't modify, just print the differences", ""),
    ("ls", "List configures files", ""),
    ("init", "Initialise a configuration file", ""),
]


@dataclass(frozen=True)
class FileType:
    """A file type handled by Nitpick."""

    text: str
    url: str
    check: Union[bool, int]
    fix: Union[bool, int]

    def __post_init__(self):
        """Warn about text that might render incorrectly."""
        if "`" in self.text:
            raise RuntimeError(f"Remove all backticks from the text: {self.text}")

    def __lt__(self, other: "FileType") -> bool:
        """Sort instances.

        From the `docs <https://docs.python.org/3/howto/sorting.html#odd-and-ends>`_:

        > It is easy to add a standard sort order to a class by defining an __lt__() method
        """
        return self.sort_key < other.sort_key

    @property
    def sort_key(self) -> str:
        """Sort key of this element."""
        return ("0" if self.text.startswith("Any") else "1") + self.text.casefold().replace(".", "")

    @property
    def text_with_url(self) -> str:
        """Text with URL in reStructuredText."""
        return f"`{self.text} <{self.url}>`_" if self.url else self.text

    def _pretty(self, attribute: str) -> str:
        value = getattr(self, attribute)
        if value is True:
            return "✅"
        if value is False:
            return "❌"
        if value == 0:
            return "❓"
        return f"`#{value} <https://github.com/andreoliwa/nitpick/issues/{value}>`_ 🚧"

    @property
    def check_str(self) -> str:
        """The check flag, as a string."""
        return self._pretty("check")

    @property
    def fix_str(self) -> str:
        """The fix flag, as a string."""
        return self._pretty("fix")

    @property
    def row(self) -> Tuple[str, str, str]:
        """Tuple for a table row."""
        return self.text_with_url, self.check_str, self.fix_str


IMPLEMENTED_FILE_TYPES: Set[FileType] = {
    FileType("Any INI file", f"{READ_THE_DOCS_URL}plugins.html#ini-files", True, True),
    FileType("Any JSON file", f"{READ_THE_DOCS_URL}plugins.html#json-files", True, 358),
    FileType("Any text file", f"{READ_THE_DOCS_URL}plugins.html#text-files", True, False),
    FileType("Any TOML file", f"{READ_THE_DOCS_URL}plugins.html#toml-files", True, True),
    FileType(EDITOR_CONFIG, f"{READ_THE_DOCS_URL}examples.html#example-editorconfig", True, True),
    FileType(PRE_COMMIT_CONFIG_YAML, f"{READ_THE_DOCS_URL}plugins.html#pre-commit-config-yaml", True, 282),
    FileType(PYLINTRC, f"{READ_THE_DOCS_URL}plugins.html#ini-files", True, True),
    FileType(PACKAGE_JSON, f"{READ_THE_DOCS_URL}examples.html#example-package-json", True, 358),
    FileType(PYPROJECT_TOML, f"{READ_THE_DOCS_URL}plugins.html#toml-files", True, True),
    FileType("requirements.txt", f"{READ_THE_DOCS_URL}plugins.html#text-files", True, False),
    FileType(SETUP_CFG, f"{READ_THE_DOCS_URL}plugins.html#ini-files", True, True),
}
PLANNED_FILE_TYPES: Set[FileType] = {
    FileType("Any Markdown file", "", 280, 0),
    FileType("Any Terraform file", "", 318, 0),
    FileType(".dockerignore", "", 8, 8),
    FileType(".gitignore", "", 8, 8),
    FileType(".travis.yml", "", 15, 15),
    FileType("Dockerfile", "", 272, 272),
    FileType("Jenkinsfile", "", 278, 0),
    FileType("Makefile", "", 277, 0),
}

nit = Nitpick.singleton().init()


class DocFile:  # pylint: disable=too-few-public-methods
    """A document file (REST or Markdown)."""

    def __init__(self, filename: str) -> None:
        self.file: Path = (DOCS_DIR / filename).resolve(True)
        if self.file.suffix == ".md":
            self.divider_start = MD_DIVIDER_START
            self.divider_end = MD_DIVIDER_END
            self.divider_from_here = MD_DIVIDER_START
        else:
            self.divider_start = RST_DIVIDER_START
            self.divider_end = RST_DIVIDER_END
            self.divider_from_here = RST_DIVIDER_FROM_HERE

    def write(self, blocks: List[str], divider_id: str = None) -> int:
        """Write content to the file."""
        old_content = self.file.read_text()
        if divider_id:
            start_marker = self.divider_start.format(divider_id)
            end_marker = self.divider_end.format(divider_id)
            start_position = old_content.index(start_marker) + len(start_marker) + 1
            end_position = old_content.index(end_marker) - 1
        else:
            start_position = old_content.index(self.divider_from_here) + len(self.divider_from_here) + 1
            end_position = 0

        new_content = old_content[:start_position]
        new_content += "\n".join(blocks)
        if end_position:
            new_content += old_content[end_position:]
        new_content = new_content.strip() + "\n"

        divider_message = f" (divider: {divider_id})" if divider_id else ""
        if old_content != new_content:
            self.file.write_text(new_content)
            click.secho(f"File {self.file}{divider_message} generated", fg="yellow")
            return 1

        click.secho(f"File {self.file}{divider_message} hasn't changed", fg="green")
        return 0


def write_examples() -> int:
    """Write examples with hardcoded TOML content."""
    template = """
        .. _example-{link}:

        {header}
        {dashes}

        Contents of `{toml_file} <{url}>`_:

        .. code-block::{language}

        {toml_content}
    """
    clean_template = dedent(template).strip()
    blocks = []
    for toml_file, header in STYLE_MAPPING.items():
        style_path = STYLES_DIR / toml_file
        toml_content = style_path.read_text().strip()
        if not toml_content:
            # Skip empty TOML styles
            continue

        base_name = str(style_path.relative_to(STYLES_DIR.parent))
        indented_lines = [("    " + line.rstrip()).rstrip() for line in toml_content.split("\n")]
        blocks.append("")
        blocks.append(
            clean_template.format(
                link=slugify(header),
                header=header,
                dashes="-" * len(header),
                toml_file=base_name,
                url=GitHubURL(PROJECT_OWNER, PROJECT_NAME, f"v{__version__}", base_name).url,
                # Skip TOML with JSON inside, to avoid this error message:
                # nitpick/docs/examples.rst:193: WARNING: Could not lex literal_block as "toml". Highlighting skipped.
                language="" if "contains_json" in toml_content else " toml",
                toml_content="\n".join(indented_lines),
            )
        )

    rv = DocFile("examples.rst").write(blocks)

    missing = SortedDict()
    for existing_toml_path in sorted(STYLES_DIR.glob("**/*.toml")):
        partial_name = str(existing_toml_path.relative_to(STYLES_DIR))
        if partial_name not in STYLE_MAPPING:
            missing[partial_name] = existing_toml_path.stem

    if missing:
        click.secho(
            f"ERROR: Add missing style files to the 'style_mapping' var in '{__file__}',"
            f" as file/header pairs. Example:",
            fg="red",
        )
        pprint(missing)
        sys.exit(1)
    return rv


def write_plugins() -> int:
    """Write plugins.rst with the docstrings from :py:class:`nitpick.plugins.base.NitpickPlugin` classes."""
    template = """
        .. _{link}:

        {header}
        {dashes}

        {description}
    """
    clean_template = dedent(template).strip()
    blocks = []

    # Sort order: classes with fixed file names first, then alphabetically by class name
    for plugin_class in sorted(
        nit.project.plugin_manager.hook.plugin_class(),  # pylint: disable=no-member
        key=lambda c: "0" if c.filename else "1" + c.__name__,
    ):
        header = plugin_class.filename
        if not header:
            # module_name = file_class.__module__
            module = import_module(plugin_class.__module__)
            header = (module.__doc__ or "").strip(" .")

        blocks.append("")
        blocks.append(
            clean_template.format(
                link=slugify(plugin_class.__name__),
                header=header,
                dashes="-" * len(header),
                description=dedent(f"    {plugin_class.__doc__}").strip(),
            )
        )
    return DocFile("plugins.rst").write(blocks)


def write_cli() -> int:
    """Write CLI docs."""
    template = """
        .. _cli_cmd{anchor}:

        {header}
        {dashes}
        {long}

        .. code-block::

        {help}
    """
    clean_template = dedent(template).strip()
    blocks = []

    for command, short, long in CLI_MAPPING:
        anchor = f"_{command}" if command else ""
        header = f"``{command}``: {short}" if command else short
        blocks.append("")
        parts = ["nitpick"]
        if command:
            parts.append(command)
        parts.append("--help")
        print(" ".join(parts))
        output = check_output(parts).decode().strip()  # nosec
        blocks.append(
            clean_template.format(
                anchor=anchor, header=header, dashes="-" * len(header), long=dedent(long), help=indent(output, "    ")
            )
        )

    return DocFile("cli.rst").write(blocks)


def write_config() -> int:
    """Write config file names."""
    blocks = [f"{index + 1}. ``{config_file}``" for index, config_file in enumerate(CONFIG_FILES)]
    blocks.insert(0, "")
    blocks.append("")
    return DocFile("configuration.rst").write(blocks, divider_id="config-file")


def write_readme(file_types: Set[FileType], divider: str) -> int:
    """Write the README."""
    rows: List[Tuple[str, ...]] = [("File type", "``nitpick check``", "``nitpick fix``")]
    for file_type in sorted(file_types):
        rows.append(file_type.row)

    blocks = [".. list-table::\n   :header-rows: 1\n"]
    for row in rows:
        template = "* - {}\n  - {}\n  - {}"
        blocks.append(indent(template.format(*row), "   "))

    return DocFile("../README.rst").write(blocks, divider_id=divider)


if __name__ == "__main__":
    sys.exit(
        write_readme(IMPLEMENTED_FILE_TYPES, "implemented")
        + write_readme(PLANNED_FILE_TYPES, "planned")
        + write_config()
        + write_examples()
        + write_plugins()
        + write_cli()
    )
