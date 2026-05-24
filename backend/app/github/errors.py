class GitHubError(Exception):
    def __init__(self, status: int, message: str, url: str | None = None) -> None:
        super().__init__(f"[{status}] {message}" + (f" ({url})" if url else ""))
        self.status = status
        self.message = message
        self.url = url


class GitHubNotFound(GitHubError):
    pass


class GitHubAuthError(GitHubError):
    pass


class GitHubRateLimited(GitHubError):
    pass


def raise_for(resp_status: int, message: str, url: str | None = None) -> None:
    if resp_status == 401 or resp_status == 403:
        if "rate limit" in message.lower():
            raise GitHubRateLimited(resp_status, message, url)
        raise GitHubAuthError(resp_status, message, url)
    if resp_status == 404:
        raise GitHubNotFound(resp_status, message, url)
    raise GitHubError(resp_status, message, url)
