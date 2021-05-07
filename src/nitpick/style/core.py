"""Style files."""
import os
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterator, Optional, Set, Tuple, Type
from urllib.parse import urljoin, urlsplit, urlunsplit

from identify import identify
from loguru import logger
from more_itertools import always_iterable
from slugify import slugify
from toml import TomlDecodeError

from nitpick import __version__, fields
from nitpick.constants import (
    CACHE_DIR_NAME,
    DOT_SLASH,
    MERGED_STYLE_TOML,
    NITPICK_STYLE_TOML,
    NITPICK_STYLES_INCLUDE_JMEX,
    PROJECT_NAME,
    PROJECT_OWNER,
    PYPROJECT_TOML,
    TOML_EXTENSION,
)
from nitpick.exceptions import QuitComplainingError, pretty_exception
from nitpick.formats import TOMLFormat
from nitpick.generic import MergeDict, is_url, search_dict
from nitpick.plugins.base import NitpickPlugin
from nitpick.plugins.info import FileInfo
from nitpick.project import Project, climb_directory_tree
from nitpick.schemas import BaseStyleSchema, flatten_marshmallow_errors
from nitpick.style.config import ConfigValidator
from nitpick.style.fetchers import StyleFetcherManager
from nitpick.style.fetchers.github import GitHubURL
from nitpick.typedefs import JsonDict, StrOrIterable, StrOrList, mypy_property
from nitpick.violations import Fuss, Reporter, StyleViolations

Plugins = Set[Type[NitpickPlugin]]


@dataclass(repr=True)
class Style:  # pylint: disable=too-many-instance-attributes
    """Include styles recursively from one another."""

    project: Project
    offline: bool
    cache_option: str

    _all_styles: MergeDict = field(init=False, default_factory=MergeDict)
    _already_included: Set[str] = field(init=False, default_factory=set)
    _first_full_path: str = ""

    _style_fetcher_manager: StyleFetcherManager = field(init=False)
    _config_validator: ConfigValidator = field(init=False)

    _dynamic_schema_class: type = field(init=False, default=BaseStyleSchema)

    def __post_init__(self) -> None:
        """Initialize dependant fields."""
        self._style_fetcher_manager = StyleFetcherManager(self.offline, self.cache_dir, self.cache_option)
        self._config_validator = ConfigValidator(self.project)
        self.rebuild_dynamic_schema()

    def __hash__(self):
        """Calculate hash on hashable items so lru_cache knows how to cache data from this class."""
        return hash((self.project, self.offline, self.cache_option))

    @mypy_property
    @lru_cache()
    def cache_dir(self) -> Path:
        """Clear the cache directory (on the project root or on the current directory)."""
        path: Path = self.project.root / CACHE_DIR_NAME / PROJECT_NAME

        # TODO: check if the merged style file is still needed; if not, this line can be removed
        path.mkdir(parents=True, exist_ok=True)

        return path

    @staticmethod
    def get_default_style_url():
        """Return the URL of the default style for the current version."""
        return GitHubURL(PROJECT_OWNER, PROJECT_NAME, f"v{__version__}", NITPICK_STYLE_TOML).raw_content_url

    def find_initial_styles(self, configured_styles: StrOrIterable) -> Iterator[Fuss]:
        """Find the initial style(s) and include them."""
        if configured_styles:
            chosen_styles: StrOrIterable = list(configured_styles)
            log_message = f"Using styles configured in {PYPROJECT_TOML}"
        else:
            paths = climb_directory_tree(self.project.root, [NITPICK_STYLE_TOML])
            if paths:
                chosen_styles = str(sorted(paths)[0])
                log_message = "Using local style found climbing the directory tree"
            else:
                chosen_styles = self.get_default_style_url()
                log_message = "Using default remote Nitpick style"
        logger.info(f"{log_message}: {chosen_styles}")

        yield from self.include_multiple_styles(chosen_styles)

    def include_multiple_styles(self, chosen_styles: StrOrIterable) -> Iterator[Fuss]:
        """Include a list of styles (or just one) into this style tree."""
        for style_uri in always_iterable(chosen_styles):
            yield from self._include_style(style_uri)

    def _include_style(self, style_uri):
        style_uri = self._normalize_style_uri(style_uri)
        style_path, file_contents = self.get_style_path(style_uri)
        if not style_path:
            return

        resolved_path = str(style_path.resolve())
        if resolved_path in self._already_included:
            return
        self._already_included.add(resolved_path)

        read_toml_dict = self._read_toml(file_contents, style_path)

        try:
            display_name = str(style_path.relative_to(self.project.root))
        except ValueError:
            display_name = style_uri

        toml_dict, validation_errors = self._config_validator.validate(read_toml_dict)

        if validation_errors:
            yield Reporter(FileInfo(self.project, display_name)).make_fuss(
                StyleViolations.INVALID_CONFIG, flatten_marshmallow_errors(validation_errors)
            )

        self._all_styles.add(toml_dict)

        sub_styles: StrOrList = search_dict(NITPICK_STYLES_INCLUDE_JMEX, toml_dict, [])
        if sub_styles:
            yield from self.include_multiple_styles(sub_styles)

    def _read_toml(self, file_contents, style_path):
        toml = TOMLFormat(string=file_contents)
        try:
            read_toml_dict = toml.as_data
        # TODO: replace by this error when using tomlkit only in the future:
        #  except TOMLKitError as err:
        except TomlDecodeError as err:
            # If the TOML itself could not be parsed, we can't go on
            raise QuitComplainingError(
                Reporter(FileInfo(self.project, style_path.name)).make_fuss(
                    StyleViolations.INVALID_TOML, exception=pretty_exception(err)
                )
            ) from err
        return read_toml_dict

    def _normalize_style_uri(self, uri):
        is_current_uri_url = is_url(uri)
        if is_current_uri_url:
            self._first_full_path = uri
            return self._append_toml_extension_url(uri)

        uri = self._append_toml_extension(uri)

        if not self._first_full_path:
            self._first_full_path = str(Path(uri).resolve().parent) + "/"
            return uri

        if self._first_full_path and not uri.startswith(DOT_SLASH):
            if os.path.isabs(uri):
                return uri

            return self._join_uri(uri)

        return uri

    def _join_uri(self, uri):
        if is_url(self._first_full_path):
            return urljoin(self._first_full_path, uri)

        return str(Path(self._first_full_path).joinpath(uri))

    def _append_toml_extension_url(self, url):
        scheme, netloc, path, query, fragment = urlsplit(url)
        path = self._append_toml_extension(path)
        return urlunsplit((scheme, netloc, path, query, fragment))

    @staticmethod
    def _append_toml_extension(path):
        if path.endswith(TOML_EXTENSION):
            return path
        return f"{path}{TOML_EXTENSION}"

    def get_style_path(self, style_uri: str) -> Tuple[Optional[Path], str]:
        """Get the style path from the URI. Add the .toml extension if it's missing."""
        clean_style_uri = style_uri.strip()
        return self._style_fetcher_manager.fetch(clean_style_uri)

    def merge_toml_dict(self) -> JsonDict:
        """Merge all included styles into a TOML (actually JSON) dictionary."""
        merged_dict = self._all_styles.merge()
        # TODO: check if the merged style file is still needed
        merged_style_path: Path = self.cache_dir / MERGED_STYLE_TOML
        toml = TOMLFormat(data=merged_dict)

        attempt = 1
        while attempt < 5:
            try:
                merged_style_path.write_text(toml.reformatted)
                break
            except OSError:
                attempt += 1

        return merged_dict

    @staticmethod
    def file_field_pair(filename: str, base_file_class: Type[NitpickPlugin]) -> Dict[str, fields.Field]:
        """Return a schema field with info from a config file class."""
        unique_filename_with_underscore = slugify(filename, separator="_")

        kwargs = {"data_key": filename}
        if base_file_class.validation_schema:
            file_field = fields.Nested(base_file_class.validation_schema, **kwargs)
        else:
            # For some files (e.g.: pyproject.toml, INI files), there is no strict schema;
            # it can be anything they allow.
            # It's out of Nitpick's scope to validate those files.
            file_field = fields.Dict(fields.String, **kwargs)
        return {unique_filename_with_underscore: file_field}

    @lru_cache()
    def load_fixed_name_plugins(self) -> Plugins:
        """Separate classes with fixed file names from classes with dynamic files names."""
        fixed_name_classes: Plugins = set()
        for plugin_class in self.project.plugin_manager.hook.plugin_class():  # pylint: disable=no-member
            if plugin_class.filename:
                fixed_name_classes.add(plugin_class)
        return fixed_name_classes

    def rebuild_dynamic_schema(self) -> None:
        """Rebuild the dynamic Marshmallow schema when needed, adding new fields that were found on the style."""
        new_files_found: Dict[str, fields.Field] = OrderedDict()

        fixed_name_classes = self.load_fixed_name_plugins()

        for subclass in fixed_name_classes:
            new_files_found.update(self.file_field_pair(subclass.filename, subclass))

        # Only recreate the schema if new fields were found.
        if new_files_found:
            self._dynamic_schema_class = type("DynamicStyleSchema", (self._dynamic_schema_class,), new_files_found)

    def _find_subclasses(self, data, handled_tags, new_files_found):
        for possible_file in data.keys():
            found_subclasses = []
            for file_tag in identify.tags_from_filename(possible_file):
                handler_subclass = handled_tags.get(file_tag)
                if handler_subclass:
                    found_subclasses.append(handler_subclass)

            for found_subclass in found_subclasses:
                new_files_found.update(self.file_field_pair(possible_file, found_subclass))
