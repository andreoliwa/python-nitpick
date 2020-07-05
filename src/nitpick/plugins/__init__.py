"""Hooks used by Nitpick pkugins."""
from typing import TYPE_CHECKING, Optional, Set

import pluggy

from nitpick.constants import PROJECT_NAME
from nitpick.typedefs import JsonDict

if TYPE_CHECKING:
    from nitpick.plugins.base import BaseFile


hookspec = pluggy.HookspecMarker(PROJECT_NAME)
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


@hookspec
def handle_config_file(  # pylint: disable=unused-argument
    config: JsonDict, file_name: str, tags: Set[str]
) -> Optional["BaseFile"]:
    """Return a BaseFile if this plugin handles the relative filename or any of its :py:package:`identify` tags."""