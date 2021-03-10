"""Enums."""
import os
from enum import Enum, IntEnum, auto

from nitpick import PROJECT_NAME


class _OptionMixin:
    """Private mixin used to test the CLI options."""

    name: str

    def as_flake8_flag(self) -> str:
        """Format the name of a flag to be used on the CLI."""
        slug = self.name.lower().replace("_", "-")
        return f"--{PROJECT_NAME}-{slug}"

    def as_envvar(self) -> str:
        """Format the name of an environment variable."""
        return f"{PROJECT_NAME.upper()}_{self.name.upper()}"

    def get_environ(self) -> str:
        """Get the value of an environment variable."""
        return os.environ.get(self.as_envvar(), "")


class OptionEnum(_OptionMixin, Enum):
    """Options to be used with the CLI."""

    OFFLINE = "Offline mode: no style will be downloaded (no HTTP requests at all)"


class CachingEnum(IntEnum):
    """Cache modes."""

    NEVER = auto()
    FOREVER = auto()
    EXPIRES = auto()
