"""Base HTTP fetcher, other fetchers can inherit from this to wrap http errors."""
from dataclasses import dataclass, field
from typing import Tuple

import click
import requests
from loguru import logger
from requests.sessions import Session

from nitpick.enums import OptionEnum
from nitpick.style.fetchers import _requests_session
from nitpick.style.fetchers.base import StyleFetcher


@dataclass(repr=True, unsafe_hash=True)
class HttpFetcher(StyleFetcher):
    """Fetch a style from an http/https server."""

    _session: Session = field(init=False)

    requires_connection = True
    protocols: Tuple[str, ...] = ("http", "https")

    def __post_init__(self):
        """Sessions should be per class as children can have custom headers or authentication."""
        self._session = _requests_session()
        self._post_hooks()

    def _post_hooks(self):
        """Dataclasses won't call post init here if another class extends it and override."""

    def _do_fetch(self, url) -> str:
        try:
            contents = self._download(url)
        except requests.ConnectionError as err:
            logger.exception(f"Request failed with {err}")
            click.secho(
                "Your network is unreachable. Fix your connection or use"
                f" {OptionEnum.OFFLINE.as_flake8_flag()} / {OptionEnum.OFFLINE.as_envvar()}=1",
                fg="red",
                err=True,
            )
            return ""
        return contents

    def _download(self, url) -> str:
        response = self._session.get(url)
        response.raise_for_status()
        return response.text
