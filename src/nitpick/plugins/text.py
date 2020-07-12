"""Text files."""
import logging
from typing import Optional, Set

from marshmallow import Schema

from nitpick import fields
from nitpick.plugins import hookimpl
from nitpick.plugins.base import BaseFile
from nitpick.schemas import help_message
from nitpick.typedefs import JsonDict, YieldFlake8Error

LOGGER = logging.getLogger(__name__)

TEXT_FILE_RTFD_PAGE = "config_files.html#text-files"


class TextItemSchema(Schema):
    """Validation schema for the object inside ``contains``."""

    error_messages = {"unknown": help_message("Unknown configuration", TEXT_FILE_RTFD_PAGE)}
    line = fields.NonEmptyString()


class TextSchema(Schema):
    """Validation schema for the text file TOML configuration."""

    error_messages = {"unknown": help_message("Unknown configuration", TEXT_FILE_RTFD_PAGE)}
    contains = fields.List(fields.Nested(TextItemSchema))


class TextFile(BaseFile):
    """Checker for any text file."""

    error_base_number = 350
    identify_tags = {"plain-text"}
    validation_schema = TextSchema

    def suggest_initial_contents(self) -> str:
        """Suggest the initial content for this missing file."""
        return "\n".join([obj.get("line") for obj in self.file_dict.get("contains", {})])

    def check_rules(self) -> YieldFlake8Error:
        """Check rules for this file. It should be overridden by inherited classes if needed."""
        # FIXME: check missing lines


@hookimpl
def handle_config_file(config: JsonDict, file_name: str, tags: Set[str]) -> Optional["BaseFile"]:
    """Handle text files."""
    return TextFile(config, file_name) if "plain-text" in tags else None
