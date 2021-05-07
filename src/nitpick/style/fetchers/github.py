"""Support for ``gh`` and ``github`` schemes."""
from dataclasses import dataclass
from enum import Enum
from typing import Tuple
from urllib.parse import urlparse, uses_netloc, uses_relative

from nitpick.style.fetchers.http import HttpFetcher


class GitHubProtocol(Enum):
    """Protocols for the GitHUb scheme."""

    SHORT = "gh"
    LONG = "github"


@dataclass()
class GitHubURL:
    """Represent a GitHub URL, created from a URL or from its parts."""

    owner: str
    repository: str
    git_reference: str
    path: str

    def __post_init__(self):
        """Remove the initial slash from the path."""
        self.path = self.path.lstrip("/")

    @property
    def url(self) -> str:
        """Default URL built from attributes."""
        return f"https://github.com/{self.owner}/{self.repository}/blob/{self.git_reference}/{self.path}"

    @property
    def raw_content_url(self) -> str:
        """Raw content URL for this path."""
        return f"https://raw.githubusercontent.com/{self.owner}/{self.repository}/{self.git_reference}/{self.path}"

    @classmethod
    def from_url(cls, url: str) -> "GitHubURL":
        """Create an instance from a URL string."""
        parsed_url = urlparse(url)
        owner, repo, _, git_reference, path = parsed_url.path.strip("/").split("/", 4)
        return cls(owner, repo, git_reference, path)

    @property
    def api_url(self) -> str:
        """API URL for this repo."""
        return f"https://api.github.com/repos/{self.owner}/{self.repository}"

    @property
    def short_protocol_url(self) -> str:
        """Short protocol URL (``gh``)."""
        return f"{GitHubProtocol.SHORT.value}://{self.owner}/{self.repository}/{self.path}"

    @property
    def long_protocol_url(self) -> str:
        """Long protocol URL (``github``)."""
        return f"{GitHubProtocol.LONG.value}://{self.owner}/{self.repository}/{self.path}"


@dataclass(repr=True, unsafe_hash=True)
class GitHubFetcher(HttpFetcher):  # pylint: disable=too-few-public-methods
    """Fetch styles from GitHub repositories."""

    _registered = False
    protocols: Tuple[str, ...] = (GitHubProtocol.SHORT.value, GitHubProtocol.LONG.value)

    def _post_hooks(self):
        self._register_on_urllib()

    @classmethod
    def _register_on_urllib(cls):
        if cls._registered:
            return

        # This is necessary so urljoin knows how to deal with custom protocols
        for protocol in cls.protocols:
            uses_relative.append(protocol)
            uses_netloc.append(protocol)

    def _download(self, url) -> str:
        parsed_url = urlparse(url)
        owner = parsed_url.netloc
        repository = str(parsed_url.path.split("/")[1])

        github_url = GitHubURL(owner, repository, "develop", parsed_url.path.replace(f"/{repository}", ""))
        github_url.git_reference = self.get_default_branch(github_url)

        return super()._download(github_url.raw_content_url)

    def get_default_branch(self, github_url: GitHubURL) -> str:
        """Get the default branch from the GitHub repo using the API."""
        response = self._session.get(github_url.api_url).json()
        return response["default_branch"]
