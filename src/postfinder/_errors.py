"""What the API said when it refused."""

from __future__ import annotations


class PostFinderError(Exception):
    """The API refused, and said why.

    The service answers RFC 7807 problem documents: a title and a detail
    written for a person to read and act on. Collapsing that into "HTTP 400"
    throws away the only part of the answer that says what to do about it.
    """

    def __init__(self, status: int, title: str = "", detail: str = ""):
        self.status = status
        self.title = title
        self.detail = detail
        message = title or f"HTTP {status}"
        if detail:
            message = f"{message}: {detail}"
        super().__init__(f"{status} {message}")


class NotFound(PostFinderError):
    """Nothing is filed under that id, slug or postcode.

    Its own class because it is an ordinary thing to hit rather than a failure.
    A suburb with no locations has no page (§12.2: never a 200 with an empty
    page), a place that closed is retired, and a postcode outside the seeded
    countries was never there. Code that walks a list of ids will meet this.
    """


class BadRequest(PostFinderError):
    """The request could not be served as written: a missing coordinate, a
    category that does not exist, a query of one character."""


class RateLimited(PostFinderError):
    """Too many requests from here.

    The API is free and keyless and asks callers to be gentle: around a
    thousand requests a month from one address, responses cached, typing
    debounced. Meeting this means backing off, and, if the volume is real,
    saying what you are building at postfinder.io/en/contact/ -- the docs say
    they will very likely help.

    ``retry_after`` is the seconds the service asked for, when it said.
    """

    def __init__(self, status: int, title: str = "", detail: str = "", retry_after: float | None = None):
        super().__init__(status, title, detail)
        self.retry_after = retry_after


def error_for(status: int, title: str = "", detail: str = "", retry_after: float | None = None) -> PostFinderError:
    if status == 404:
        return NotFound(status, title, detail)
    if status == 429:
        return RateLimited(status, title, detail, retry_after)
    if 400 <= status < 500:
        return BadRequest(status, title, detail)
    return PostFinderError(status, title, detail)
