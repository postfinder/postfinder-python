"""The client itself."""

from __future__ import annotations

import ipaddress
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Sequence

from ._errors import PostFinderError, error_for
from ._models import (
    CATEGORIES,
    CategoryHub,
    CountryDetail,
    CountrySummary,
    LocalityDetail,
    NearbyPlace,
    PlaceDetail,
    PostcodeDetail,
    PostcodeIndex,
    RegionDetail,
    SearchHit,
)

__version__ = "0.1.1"

DEFAULT_BASE_URL = "https://api.postfinder.io"

#: The site answers an empty list below this, so there is nothing to ask for.
MIN_QUERY = 2

#: (method, url, headers, timeout) -> (status, body bytes)
Transport = Callable[[str, str, dict, float], "tuple[int, bytes]"]

# Bounded reads. A country's postcode index is the largest answer here and runs
# to a few megabytes; past that, something on the other end of the socket is
# not this API and a client should not be talked into reading it all.
_MAX_BODY = 32 << 20


class _SameOriginRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to the same host over https.

    Nothing here carries a credential, but a query string does carry what
    somebody typed -- which is often their own street address. A redirect to
    another host, or down to plaintext, would hand that to whoever answered.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old = urllib.parse.urlparse(req.full_url)
        new = urllib.parse.urlparse(newurl)
        if new.scheme != old.scheme or new.netloc != old.netloc:
            raise urllib.error.HTTPError(
                req.full_url, code,
                f"postfinder: refused a redirect to {new.scheme}://{new.netloc}",
                headers, fp,
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_SameOriginRedirects)


def _urllib_transport(method: str, url: str, headers: dict, timeout: float):
    req = urllib.request.Request(url, method=method, headers=headers)
    try:
        with _opener.open(req, timeout=timeout) as res:
            return res.status, res.read(_MAX_BODY)
    except urllib.error.HTTPError as err:
        return err.code, err.read(_MAX_BODY)


def _check_base_url(raw: str) -> str:
    """Refuse a base URL that would put the request somewhere it should not go.

    https always, and plaintext http only to loopback, which is what a local
    proxy and a test server need. The queries this client sends are what a
    person typed into a search box, and in this product that is frequently
    their own address.
    """
    if not raw:
        raise ValueError("postfinder: no base URL")

    parsed = urllib.parse.urlparse(raw)
    if not parsed.scheme or not parsed.hostname:
        raise ValueError(f"postfinder: base URL {raw!r} is not absolute")
    # https://api.postfinder.io:pass@evil.example reads as the real host to
    # anyone skimming a config file, and is a different host to urllib.
    # Nothing here needs userinfo, so a URL carrying it is a mistake or a trick.
    if parsed.username or parsed.password:
        raise ValueError(
            f"postfinder: base URL {raw!r} carries credentials, and the host it "
            "would reach is not the one it reads as"
        )
    if parsed.scheme == "https":
        return raw.rstrip("/")
    if parsed.scheme == "http" and _is_loopback(parsed.hostname):
        return raw.rstrip("/")
    if parsed.scheme == "http":
        raise ValueError(
            f"postfinder: base URL {raw!r} is plaintext http to a public host, "
            "which would send what people type in the clear"
        )
    raise ValueError(
        f"postfinder: base URL {raw!r} has scheme {parsed.scheme!r}, want https"
    )


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _segment(value: str, what: str) -> str:
    """One path segment, encoded.

    ``safe=""`` so a slug carrying a slash or a dot cannot walk up the path and
    reach an endpoint on another prefix. The API separates its products by path
    prefix, which makes this the boundary rather than a nicety.
    """
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"postfinder: no {what}")
    return urllib.parse.quote(text, safe="")


class PostFinder:
    """A client for the PostFinder directory API.

    Post offices, post boxes, express post boxes, parcel lockers, drop off
    points and collection points, plus the suburbs and postcodes they sit in.

        >>> from postfinder import PostFinder
        >>> pf = PostFinder()
        >>> for p in pf.nearby(-37.7404, 144.9633, category="post-offices",
        ...                    country="australia"):
        ...     print(p.name, p.distance_m, "m")

    No key and nothing to buy: the API is free, anonymous and cached at the
    edge. It does ask callers to be gentle -- roughly a thousand requests a
    month from one address, and results kept rather than re-fetched. Pass
    ``contact`` with a URL or an email and it travels in the User-Agent, so a
    conversation can start before a rate limit does.

    Attribution travels with the data: locations from OpenStreetMap (ODbL),
    localities and postcodes from GeoNames (CC BY 4.0). Publishing what you get
    back means carrying those credits. See postfinder.io/en/legal/.

    Thread safe. Make one and keep it.
    """

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        contact: str = "",
        timeout: float = 15.0,
        transport: Transport | None = None,
    ):
        self._base_url = _check_base_url(base_url)
        self._timeout = timeout
        self._transport = transport or _urllib_transport
        agent = f"postfinder-python/{__version__}"
        contact = (contact or "").strip()
        if contact:
            # contact lands in a header. A newline there is a header the caller
            # did not write, and a control character is not part of a URL or an
            # email address either way.
            if any(c in contact for c in "\r\n\0") or not contact.isprintable():
                raise ValueError(
                    "postfinder: contact must be one line of printable text, "
                    "a URL or an email address"
                )
            agent = f"{agent} (+{contact})"
        self._agent = agent

    # -- finding something ------------------------------------------------

    def search(self, term: str, limit: int | None = None) -> "list[SearchHit]":
        """Suburbs and locations matching what somebody has typed.

        The typeahead. Rows come back most useful first and each carries enough
        to link to the page it names. Debounce by at least 150ms: firing on
        every keystroke spends bandwidth for no better answer.

        A term shorter than two characters returns an empty list without a
        request, which is what the service would answer anyway.
        """
        term = (term or "").strip()
        if len(term) < MIN_QUERY:
            return []
        body = self._get("/v1/search", {"q": term, "limit": limit})
        return [SearchHit.from_json(h) for h in body.get("data") or []]

    def nearby(
        self,
        lat: float,
        lng: float,
        *,
        category: str,
        country: str,
    ) -> "list[NearbyPlace]":
        """The closest locations of one category to a coordinate, nearest first.

        Within 50km and at most 30 rows, which is the question "where is the
        nearest one" rather than "list everything in the state".

        ``category`` is one of :data:`CATEGORIES`. ``country`` is the slug the
        site's URLs use: ``australia``, ``new-zealand``, ``united-kingdom``,
        ``united-states``.
        """
        if category not in CATEGORIES:
            raise ValueError(
                f"postfinder: {category!r} is not a category; use one of "
                + ", ".join(CATEGORIES)
            )
        lat, lng = self._coordinate(lat, lng)
        body = self._get(
            "/v1/nearby",
            {"lat": lat, "lng": lng, "category": category, "country": self._slug(country, "country")},
        )
        return [NearbyPlace.from_json(p) for p in body.get("data") or []]

    def place(self, public_id: str) -> PlaceDetail:
        """One location by its public id, with what is near it.

        The id is permanent: it is minted once and never derived from a source
        record, so a feed that renumbers its rows does not change it. Store
        this rather than a name or a path.

        Raises :class:`NotFound` when nothing is filed under it.
        """
        body = self._get(f"/v1/places/{_segment(public_id, 'place id')}", None)
        return PlaceDetail.from_json(body.get("data") or {})

    # -- browsing ---------------------------------------------------------

    def countries(self) -> "list[CountrySummary]":
        """Every country with pages, and how much is in each."""
        body = self._get("/v1/countries", None)
        return [CountrySummary.from_json(c) for c in body.get("data") or []]

    def country(self, country: str) -> CountryDetail:
        """One country and its states or regions."""
        body = self._get(f"/v1/countries/{self._slug(country, 'country')}", None)
        return CountryDetail.from_json(body.get("data") or {})

    def region(
        self, country: str, region: str, *, limit: int | None = None, offset: int | None = None
    ) -> RegionDetail:
        """One state or region and its localities, a page at a time.

        ``locality_total`` on the answer is every locality in the region, so a
        caller can page without asking twice.
        """
        body = self._get(
            f"/v1/countries/{self._slug(country, 'country')}"
            f"/regions/{self._slug(region, 'region')}",
            {"limit": limit, "offset": offset},
        )
        return RegionDetail.from_json(body.get("data") or {})

    def locality(self, country: str, region: str, locality: str) -> LocalityDetail:
        """One suburb: its locations, its neighbours, and what to filter by.

        Raises :class:`NotFound` for a suburb with no locations: those have no
        page, deliberately.
        """
        body = self._get(
            f"/v1/localities/{self._slug(country, 'country')}"
            f"/{self._slug(region, 'region')}"
            f"/{self._slug(locality, 'locality')}",
            None,
        )
        return LocalityDetail.from_json(body.get("data") or {})

    def category(self, country: str, category: str, *, region: str = "") -> CategoryHub:
        """One category across a country: counts per state, busiest suburbs.

        Not a national list of every post box, which would be tens of thousands
        of rows and useful to nobody.
        """
        body = self._get(
            f"/v1/countries/{self._slug(country, 'country')}"
            f"/categories/{self._slug(category, 'category')}",
            {"region": region},
        )
        return CategoryHub.from_json(body.get("data") or {})

    # -- postcodes --------------------------------------------------------

    def postcodes(self, country: str) -> PostcodeIndex:
        """Every postcode in a country, grouped by state.

        One response, meant to be kept: it is the whole index, and
        :meth:`PostcodeIndex.suburbs_in` answers from it without another call.
        """
        body = self._get(f"/v1/countries/{self._slug(country, 'country')}/postcodes", None)
        return PostcodeIndex.from_json(body.get("data") or {})

    def postcode(self, country: str, postcode: str) -> PostcodeDetail:
        """The suburbs one postcode covers, busiest first.

        A postcode is not a suburb: 3058 is Coburg, Coburg North and
        Merlynston, and an address in any of them is written with the same four
        digits.

        Three to five digits. Letters are a different problem -- the UK and
        Canada -- and the service does not take them, so neither does this.
        """
        code = str(postcode or "").strip()
        if not (3 <= len(code) <= 5) or not code.isdigit():
            raise ValueError(
                f"postfinder: {postcode!r} is not a postcode this API takes; "
                "three to five digits"
            )
        body = self._get(
            f"/v1/countries/{self._slug(country, 'country')}/postcodes/{code}", None
        )
        return PostcodeDetail.from_json(body.get("data") or {})

    # -- plumbing ---------------------------------------------------------

    @staticmethod
    def _coordinate(lat: Any, lng: Any) -> "tuple[float, float]":
        try:
            lat, lng = float(lat), float(lng)
        except (TypeError, ValueError):
            raise ValueError("postfinder: lat and lng must be numbers") from None
        # NaN fails every comparison, which is why this is written as a range
        # check that it cannot pass.
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            raise ValueError(
                f"postfinder: ({lat}, {lng}) is not a point on the globe; "
                "lat -90..90, lng -180..180"
            )
        return lat, lng

    @staticmethod
    def _slug(value: str, what: str) -> str:
        return _segment(value, what)

    def _get(self, path: str, params: "dict | None") -> dict:
        url = self._base_url + path
        query = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        if query:
            url += "?" + urllib.parse.urlencode(query)

        status, raw = self._transport(
            "GET",
            url,
            {
                "Accept": "application/json",
                "User-Agent": self._agent,
            },
            self._timeout,
        )

        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            body = {}
        if not isinstance(body, dict):
            body = {}

        if not 200 <= status < 300:
            raise error_for(status, body.get("title", ""), body.get("detail", ""))
        return body
