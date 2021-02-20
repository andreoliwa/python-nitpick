"""Enforce config on `setup.cfg <https://docs.python.org/3/distutils/configfile.html>`."""
from configparser import ConfigParser
from io import StringIO
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple, Type

import dictdiffer
from configupdater import ConfigUpdater

from nitpick.constants import SETUP_CFG
from nitpick.plugins import hookimpl
from nitpick.plugins.base import NitpickPlugin
from nitpick.plugins.data import FileData
from nitpick.violations import Fuss, ViolationEnum

COMMA_SEPARATED_VALUES = "comma_separated_values"
SECTION_SEPARATOR = "."


class Violations(ViolationEnum):
    """Violations for this plugin."""

    MissingSections = (321, " has some missing sections. Use this:")
    MissingValuesInList = (322, " has missing values in the {key!r} key. Include those values:")
    KeyHasDifferentValue = (323, ": [{section}]{key} is {actual} but it should be like this:")
    MissingKeyValuePairs = (324, ": section [{section}] has some missing key/value pairs. Use this:")
    InvalidCommaSeparatedValuesSection = (325, f": invalid sections on {COMMA_SEPARATED_VALUES}:")


class SetupCfgPlugin(NitpickPlugin):
    """Enforce config on `setup.cfg <https://docs.python.org/3/distutils/configfile.html>`_.

    Example: :ref:`flake8 configuration <default-flake8>`.
    """

    filename = SETUP_CFG
    violation_base_code = 320

    parser: ConfigParser
    updater: ConfigUpdater
    comma_separated_values: Set[str]

    def init(self):
        """Post initialization after the instance was created."""
        self.parser = ConfigParser()
        self.updater = ConfigUpdater()
        self.comma_separated_values = set(self.nitpick_file_dict.get(COMMA_SEPARATED_VALUES, []))

    @property
    def current_sections(self) -> Set[str]:
        """Current sections of the .ini file, inclusing updated sections."""
        return set(self.updater.sections())

    @property
    def initial_contents(self) -> str:
        """Suggest the initial content for this missing file."""
        return self.get_missing_output()

    @property
    def expected_sections(self) -> Set[str]:
        """Expected sections (from the style config)."""
        return set(self.file_dict.keys())

    def missing_sections_compared_to(self, sections: Set[str] = None):
        """Return the missing sections when compared to another set of sections."""
        return

    def write_file(self, file_exists: bool) -> None:
        """Write the new file."""
        if file_exists:
            self.updater.update_file()
        else:
            self.updater.write(self.file_path.open("w"))

    def get_missing_output(self) -> str:
        """Get a missing output string example from the missing sections in setup.cfg."""
        missing = self.expected_sections - self.current_sections
        if not missing:
            return ""

        missing_cfg = ConfigParser()
        for section in sorted(missing):
            expected_config: Dict = self.file_dict[section]
            if self.apply:
                if self.updater.last_item:
                    self.updater.last_item.add_after.space(1)
                self.updater.add_section(section)
                self.updater[section].update(expected_config)
            missing_cfg[section] = expected_config
        return self.get_example_cfg(missing_cfg)

    def enforce_rules(self) -> Iterator[Fuss]:
        """Enforce rules on missing sections and missing key/value pairs in setup.cfg."""
        with self.file_path.open() as handle:
            self.parser.read_file(handle)
        self.updater.read(str(self.file_path))

        # TODO: convert the contents to dict (with IniConfig().sections?) and mimic other plugins doing dict diffs
        missing = self.get_missing_output()
        if missing:
            yield self.reporter.make_fuss(Violations.MissingSections, missing, self.apply)

        csv_sections = {v.split(".")[0] for v in self.comma_separated_values}
        missing_csv = csv_sections.difference(self.current_sections)
        if missing_csv:
            yield self.reporter.make_fuss(Violations.InvalidCommaSeparatedValuesSection, ", ".join(sorted(missing_csv)))

        for section in self.expected_sections - self.current_sections:
            expected_dict = self.file_dict[section]
            actual_dict = dict(self.parser[section])
            # TODO: add a class Ini(BaseFormat) and move this dictdiffer code there
            for diff_type, key, values in dictdiffer.diff(actual_dict, expected_dict):
                if diff_type == dictdiffer.CHANGE:
                    yield from self.compare_different_keys(section, key, values[0], values[1])
                elif diff_type == dictdiffer.ADD:
                    yield from self.show_missing_keys(section, key, values)

    def compare_different_keys(self, section, key, raw_actual: Any, raw_expected: Any) -> Iterator[Fuss]:
        """Compare different keys, with special treatment when they are lists or numeric."""
        combined = f"{section}.{key}"
        if combined in self.comma_separated_values:
            # The values might contain spaces
            actual_set = {s.strip() for s in raw_actual.split(",")}
            expected_set = {s.strip() for s in raw_expected.split(",")}
            missing = expected_set - actual_set
            if missing:
                joined_values = ",".join(sorted(missing))
                value_to_append = f",{joined_values}"
                if self.apply:
                    self.updater[section][key].value += value_to_append
                yield self.reporter.make_fuss(
                    Violations.MissingValuesInList, f"[{section}]\n{key} = (...){value_to_append}", key=key, fixed=True
                )
            return

        if isinstance(raw_actual, (int, float, bool)) or isinstance(raw_expected, (int, float, bool)):
            # A boolean "True" or "true" has the same effect on setup.cfg.
            actual = str(raw_actual).lower()
            expected = str(raw_expected).lower()
        else:
            actual = raw_actual
            expected = raw_expected
        if actual != expected:
            if self.apply:
                self.updater[section][key].value = expected
            yield self.reporter.make_fuss(
                Violations.KeyHasDifferentValue,
                f"[{section}]\n{key} = {raw_expected}",
                section=section,
                key=key,
                actual=raw_actual,
                fixed=self.apply,
            )

    def show_missing_keys(  # pylint: disable=unused-argument
        self, section, key, values: List[Tuple[str, Any]]
    ) -> Iterator[Fuss]:
        """Show the keys that are not present in a section."""
        parser = ConfigParser()
        missing_dict = dict(values)
        parser[section] = missing_dict
        output = self.get_example_cfg(parser)
        if self.apply:
            self.updater[section].update(missing_dict)
        yield self.reporter.make_fuss(Violations.MissingKeyValuePairs, output, self.apply, section=section)

    @staticmethod
    def get_example_cfg(config_parser: ConfigParser) -> str:
        """Print an example of a config parser in a string instead of a file."""
        string_stream = StringIO()
        config_parser.write(string_stream)
        output = string_stream.getvalue().strip()
        return output


@hookimpl
def plugin_class() -> Type["NitpickPlugin"]:
    """You should return your plugin class here."""
    return SetupCfgPlugin


@hookimpl
def can_handle(data: FileData) -> Optional[Type["NitpickPlugin"]]:
    """Handle the setup.cfg file."""
    if data.path_from_root == SETUP_CFG:
        return SetupCfgPlugin
    return None
