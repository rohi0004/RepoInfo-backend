"""Git URL parsing helpers."""

import re
from dataclasses import dataclass


@dataclass(slots=True)
class GitLocation:
    provider: str
    owner: str
    name: str
    full_name: str
    clone_url: str
    web_url: str


_GITHUB = re.compile(r"^(?:https?://)?(?:www\.)?github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")
_GITLAB = re.compile(r"^(?:https?://)?(?:www\.)?gitlab\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")
_BITBUCKET = re.compile(r"^(?:https?://)?(?:www\.)?bitbucket\.org/([^/]+)/([^/]+?)(?:\.git)?/?$")


def parse_git_url(url: str) -> GitLocation:
    url = url.strip()
    for provider, pattern, host in (
        ("github", _GITHUB, "github.com"),
        ("gitlab", _GITLAB, "gitlab.com"),
        ("bitbucket", _BITBUCKET, "bitbucket.org"),
    ):
        m = pattern.match(url)
        if m:
            owner, name = m.group(1), m.group(2)
            return GitLocation(
                provider=provider,
                owner=owner,
                name=name,
                full_name=f"{owner}/{name}",
                clone_url=f"https://{host}/{owner}/{name}.git",
                web_url=f"https://{host}/{owner}/{name}",
            )
    raise ValueError(f"Unsupported repository URL: {url}")
