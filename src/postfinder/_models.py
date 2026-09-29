"""The shapes the API returns.

Every model is a frozen dataclass with a ``from_json``, and every one ignores a
field it does not know: the service may add one before this library learns the
name, and a client that raises on an unrecognised key turns a compatible change
at the service into an outage in somebody's nightly job.

Several models carry a ``path``. That is the page on postfinder.io the row
names, built from the slugs the row already carries, so a caller linking to the
site does not need a second request to find out where a result lives.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime
from typing import Any, Mapping, Sequence

#: The categories /v1/nearby accepts. Anything else is a 400, so the client
#: checks the name before spending a request on it.
CATEGORIES = (
    "post-offices",
    "post-boxes",
    "express-post-boxes",
    "parcel-lockers",
    "drop-off-points",
    "collection-points",
)

#: The site serves one language today and its paths carry the prefix.
_LANG = "en"

# Field names per class, worked out once. Parsing a country's postcode index
# means building tens of thousands of these, and dataclasses.fields() walks the
# MRO on every call.
_KNOWN: "dict[type, frozenset]" = {}


def _only_known(cls, raw: Mapping[str, Any] | None) -> dict:
    known = _KNOWN.get(cls)
    if known is None:
        known = _KNOWN[cls] = frozenset(f.name for f in fields(cls))
    return {k: v for k, v in (raw or {}).items() if k in known}


def _stamp(value: Any) -> "datetime | None":
    """RFC 3339 to datetime, or None.

    A timestamp that will not parse is one field of one row; dropping it beats
    refusing a record that is otherwise complete.
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def locality_path(country: str, region: str, locality: str) -> str:
    """The suburb page: /en/australia/victoria/coburg/."""
    if not (country and region and locality):
        return ""
    return f"/{_LANG}/{country}/{region}/{locality}/"


def place_path(country: str, region: str, locality: str, brand: str, slug: str) -> str:
    """The location page, which carries the brand as a segment.

    A place with no brand is filed under ``unbranded``, which is what the
    server stores rather than a special case invented here.
    """
    if not (country and region and locality and slug):
        return ""
    return f"/{_LANG}/{country}/{region}/{locality}/{brand or 'unbranded'}/{slug}/"


@dataclass(frozen=True)
class Country:
    iso2: str = ""
    slug: str = ""
    name: str = ""

    @property
    def path(self) -> str:
        return f"/{_LANG}/{self.slug}/" if self.slug else ""

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "Country":
        return cls(**_only_known(cls, raw))


@dataclass(frozen=True)
class Region:
    slug: str = ""
    #: The state or territory code where the country has them: VIC, NSW.
    code: str = ""
    name: str = ""

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "Region":
        return cls(**_only_known(cls, raw))


@dataclass(frozen=True)
class Locality:
    """One suburb, town or locality."""

    slug: str = ""
    name: str = ""
    postcode: str = ""
    lat: float | None = None
    lng: float | None = None
    place_count: int = 0

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "Locality":
        return cls(**_only_known(cls, raw))


@dataclass(frozen=True)
class Place:
    """One location: a post office, a post box, a parcel locker.

    ``brand`` and ``category`` are keys rather than prose -- ``australia-post``,
    ``parcel-lockers`` -- because they are what the site's own URLs and filters
    are built from. ``brand`` is ``unbranded`` where a location has none.
    """

    public_id: str = ""
    slug: str = ""
    name: str = ""
    brand: str = ""
    category: str = ""
    address: str = ""
    lat: float = 0.0
    lng: float = 0.0
    #: Opening hours as the source published them, where there are any. Most
    #: post boxes have none.
    hours: "dict[str, Any]" = field(default_factory=dict)
    attributes: "dict[str, Any]" = field(default_factory=dict)
    last_verified_at: "datetime | None" = None
    closed_at: "datetime | None" = None

    @property
    def closed(self) -> bool:
        return self.closed_at is not None

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "Place":
        data = _only_known(cls, raw)
        data["last_verified_at"] = _stamp(data.get("last_verified_at"))
        data["closed_at"] = _stamp(data.get("closed_at"))
        data["hours"] = data.get("hours") or {}
        data["attributes"] = data.get("attributes") or {}
        return cls(**data)


@dataclass(frozen=True)
class NearbyPlace:
    """A place with how far away it is, from /v1/nearby.

    Carries the slugs of where it sits, so this one is the row that can build
    its own page path.
    """

    place: Place = field(default_factory=Place)
    country: str = ""
    region: str = ""
    locality: str = ""
    distance_km: float = 0.0

    # The place's own fields, readable without reaching through .place: this is
    # the row people iterate over.
    @property
    def public_id(self) -> str:
        return self.place.public_id

    @property
    def name(self) -> str:
        return self.place.name

    @property
    def brand(self) -> str:
        return self.place.brand

    @property
    def category(self) -> str:
        return self.place.category

    @property
    def address(self) -> str:
        return self.place.address

    @property
    def lat(self) -> float:
        return self.place.lat

    @property
    def lng(self) -> float:
        return self.place.lng

    @property
    def hours(self) -> "dict[str, Any]":
        return self.place.hours

    @property
    def closed(self) -> bool:
        return self.place.closed

    @property
    def distance_m(self) -> int:
        """Metres, rounded. What a page prints: "420 m", not "0.42 km"."""
        return int(round(self.distance_km * 1000))

    @property
    def path(self) -> str:
        return place_path(self.country, self.region, self.locality, self.place.brand, self.place.slug)

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "NearbyPlace":
        raw = raw or {}
        return cls(
            place=Place.from_json(raw),
            country=raw.get("country", "") or "",
            region=raw.get("region", "") or "",
            locality=raw.get("locality", "") or "",
            distance_km=float(raw.get("distance_km") or 0.0),
        )


@dataclass(frozen=True)
class SearchHit:
    """One row of the typeahead: a suburb or a location.

    ``kind`` says which, and the fields that only make sense for one of them
    are empty on the other. A hit of kind ``address`` exists in the shape but
    not in this API's answers: api.postfinder.io filters street address
    rows out.
    """

    kind: str = ""
    slug: str = ""
    name: str = ""
    country: str = ""
    region: str = ""
    locality: str = ""
    #: The suburb's name as text, for a row whose suburb has no page yet.
    locality_name: str = ""
    state: str = ""
    postcode: str = ""
    place_count: int = 0
    lat: float | None = None
    lng: float | None = None
    score: float = 0.0
    gnaf_pid: str = ""

    @property
    def path(self) -> str:
        """The page this row links to.

        A suburb row links to its own page. A place row links to its suburb,
        because a location's path carries a brand segment and a search row does
        not carry the brand key: :meth:`PostFinder.place` returns the exact one.
        """
        if self.kind == "locality":
            return locality_path(self.country, self.region, self.slug)
        if self.kind == "place":
            return locality_path(self.country, self.region, self.locality)
        return ""

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "SearchHit":
        return cls(**_only_known(cls, raw))


@dataclass(frozen=True)
class CountrySummary:
    iso2: str = ""
    slug: str = ""
    name: str = ""
    region_count: int = 0
    locality_count: int = 0
    place_count: int = 0

    @property
    def path(self) -> str:
        return f"/{_LANG}/{self.slug}/" if self.slug else ""

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "CountrySummary":
        return cls(**_only_known(cls, raw))


@dataclass(frozen=True)
class RegionSummary:
    slug: str = ""
    code: str = ""
    name: str = ""
    locality_count: int = 0
    #: On a category hub this counts that category only, not the region total.
    place_count: int = 0

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "RegionSummary":
        return cls(**_only_known(cls, raw))


@dataclass(frozen=True)
class LocalitySummary:
    slug: str = ""
    name: str = ""
    postcode: str = ""
    place_count: int = 0

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "LocalitySummary":
        return cls(**_only_known(cls, raw))


@dataclass(frozen=True)
class Facet:
    """A key and how many rows carry it, for a filter that offers what exists."""

    key: str = ""
    count: int = 0

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "Facet":
        return cls(**_only_known(cls, raw))


@dataclass(frozen=True)
class LocalityLink:
    """A suburb, with enough to link to it and how far it is from here."""

    country: str = ""
    region: str = ""
    slug: str = ""
    name: str = ""
    place_count: int = 0
    distance_km: float = 0.0

    @property
    def path(self) -> str:
        return locality_path(self.country, self.region, self.slug)

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "LocalityLink":
        return cls(**_only_known(cls, raw))


@dataclass(frozen=True)
class PlaceLink:
    """A location near another one, on a place page."""

    public_id: str = ""
    slug: str = ""
    name: str = ""
    brand: str = ""
    category: str = ""
    address: str = ""
    country: str = ""
    region: str = ""
    locality: str = ""
    distance_km: float = 0.0

    @property
    def distance_m(self) -> int:
        return int(round(self.distance_km * 1000))

    @property
    def path(self) -> str:
        return place_path(self.country, self.region, self.locality, self.brand, self.slug)

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "PlaceLink":
        return cls(**_only_known(cls, raw))


@dataclass(frozen=True)
class ReviewSummary:
    count: int = 0
    average: float | None = None
    last_as_listed_at: "datetime | None" = None

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "ReviewSummary":
        data = _only_known(cls, raw)
        data["last_as_listed_at"] = _stamp(data.get("last_as_listed_at"))
        return cls(**data)


@dataclass(frozen=True)
class Review:
    """One approved review. Moderated before it is served (§17)."""

    id: int = 0
    name: str = ""
    #: What happened when they went: the site asks that rather than only stars.
    outcome: str = ""
    rating: int | None = None
    body: str = ""
    created_at: "datetime | None" = None

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "Review":
        data = _only_known(cls, raw)
        data["created_at"] = _stamp(data.get("created_at"))
        return cls(**data)


@dataclass(frozen=True)
class Reviews:
    summary: ReviewSummary = field(default_factory=ReviewSummary)
    recent: "tuple[Review, ...]" = ()

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "Reviews":
        raw = raw or {}
        return cls(
            summary=ReviewSummary.from_json(raw.get("summary")),
            recent=tuple(Review.from_json(r) for r in raw.get("recent") or ()),
        )


@dataclass(frozen=True)
class Photo:
    """An approved photo of a place."""

    id: str = ""
    credit: str = ""
    licence: str = ""
    width: int = 0
    height: int = 0
    created_at: "datetime | None" = None

    @property
    def path(self) -> str:
        """Where the site serves it, which is also where the API does."""
        return f"/v1/photos/{self.id}" if self.id else ""

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "Photo":
        data = _only_known(cls, raw)
        data["created_at"] = _stamp(data.get("created_at"))
        return cls(**data)


@dataclass(frozen=True)
class CountryDetail:
    country: Country = field(default_factory=Country)
    regions: "tuple[RegionSummary, ...]" = ()

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "CountryDetail":
        raw = raw or {}
        return cls(
            country=Country.from_json(raw.get("country")),
            regions=tuple(RegionSummary.from_json(r) for r in raw.get("regions") or ()),
        )


@dataclass(frozen=True)
class RegionDetail:
    country: Country = field(default_factory=Country)
    region: Region = field(default_factory=Region)
    localities: "tuple[LocalitySummary, ...]" = ()
    #: Every locality in the region, not just this page of them.
    locality_total: int = 0

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "RegionDetail":
        raw = raw or {}
        return cls(
            country=Country.from_json(raw.get("country")),
            region=Region.from_json(raw.get("region")),
            localities=tuple(LocalitySummary.from_json(l) for l in raw.get("localities") or ()),
            locality_total=int(raw.get("locality_total") or 0),
        )


@dataclass(frozen=True)
class CategoryHub:
    """One category across a country: "parcel lockers in Australia".

    Counts rather than locations. A national list of every post box is tens of
    thousands of rows and useful to nobody; what a reader needs is which state,
    then which suburb.
    """

    country: Country = field(default_factory=Country)
    category: str = ""
    total: int = 0
    regions: "tuple[RegionSummary, ...]" = ()
    #: The busiest suburbs for this category, so a page opens with somewhere
    #: worth clicking.
    localities: "tuple[LocalityLink, ...]" = ()

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "CategoryHub":
        raw = raw or {}
        return cls(
            country=Country.from_json(raw.get("country")),
            category=raw.get("category", "") or "",
            total=int(raw.get("total") or 0),
            regions=tuple(RegionSummary.from_json(r) for r in raw.get("regions") or ()),
            localities=tuple(LocalityLink.from_json(l) for l in raw.get("localities") or ()),
        )


@dataclass(frozen=True)
class PostcodeEntry:
    """One suburb and the postcode people write for it."""

    postcode: str = ""
    slug: str = ""
    name: str = ""
    place_count: int = 0

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "PostcodeEntry":
        return cls(**_only_known(cls, raw))


@dataclass(frozen=True)
class RegionPostcodes:
    region: Region = field(default_factory=Region)
    entries: "tuple[PostcodeEntry, ...]" = ()

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "RegionPostcodes":
        raw = raw or {}
        return cls(
            region=Region.from_json(raw.get("region")),
            entries=tuple(PostcodeEntry.from_json(e) for e in raw.get("entries") or ()),
        )


@dataclass(frozen=True)
class PostcodeIndex:
    """Every postcode in a country, grouped by state.

    The whole index arrives in one response because that is how a postcode list
    is read and what makes it cacheable. Fetch it once and keep it.
    """

    country: Country = field(default_factory=Country)
    total: int = 0
    regions: "tuple[RegionPostcodes, ...]" = ()

    def suburbs_in(self, postcode: str) -> "tuple[PostcodeEntry, ...]":
        """The suburbs one postcode covers, without a request.

        A postcode is not a suburb: 3058 is Coburg, Coburg North and
        Merlynston. The map is built on the first call and kept, so looking up
        a column of ten thousand postcodes costs one pass over the index rather
        than ten thousand.
        """
        table = self._by_postcode
        if table is None:
            table = {}
            for group in self.regions:
                for entry in group.entries:
                    table.setdefault(entry.postcode, []).append(entry)
            table = {code: tuple(rows) for code, rows in table.items()}
            # Frozen so a parsed answer cannot be edited by accident; the cache
            # is not part of the value and is not compared or printed.
            object.__setattr__(self, "_by_postcode", table)
        return table.get(str(postcode).strip(), ())

    #: Built by suburbs_in on first use.
    _by_postcode: "dict[str, tuple[PostcodeEntry, ...]] | None" = field(
        default=None, compare=False, repr=False
    )

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "PostcodeIndex":
        raw = raw or {}
        return cls(
            country=Country.from_json(raw.get("country")),
            total=int(raw.get("total") or 0),
            regions=tuple(RegionPostcodes.from_json(r) for r in raw.get("regions") or ()),
        )


@dataclass(frozen=True)
class PostcodeDetail:
    """One postcode and the suburbs it covers, busiest first."""

    country: Country = field(default_factory=Country)
    region: Region = field(default_factory=Region)
    postcode: str = ""
    #: Locations across every suburb in the postcode.
    total: int = 0
    localities: "tuple[LocalityLink, ...]" = ()

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "PostcodeDetail":
        raw = raw or {}
        return cls(
            country=Country.from_json(raw.get("country")),
            region=Region.from_json(raw.get("region")),
            postcode=raw.get("postcode", "") or "",
            total=int(raw.get("total") or 0),
            localities=tuple(LocalityLink.from_json(l) for l in raw.get("localities") or ()),
        )


@dataclass(frozen=True)
class LocalityDetail:
    """One suburb: what is in it, and what to filter by."""

    country: Country = field(default_factory=Country)
    region: Region = field(default_factory=Region)
    locality: Locality = field(default_factory=Locality)
    #: Categories present here, with counts: what a filter should offer.
    categories: "tuple[Facet, ...]" = ()
    brands: "tuple[Facet, ...]" = ()
    places: "tuple[Place, ...]" = ()
    neighbours: "tuple[LocalityLink, ...]" = ()

    @property
    def path(self) -> str:
        return locality_path(self.country.slug, self.region.slug, self.locality.slug)

    def count_of(self, category: str) -> int:
        """How many locations of one category are here, zero if none."""
        for facet in self.categories:
            if facet.key == category:
                return facet.count
        return 0

    def path_of(self, place: Place) -> str:
        """The page path for one of this suburb's places."""
        return place_path(self.country.slug, self.region.slug, self.locality.slug, place.brand, place.slug)

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "LocalityDetail":
        raw = raw or {}
        return cls(
            country=Country.from_json(raw.get("country")),
            region=Region.from_json(raw.get("region")),
            locality=Locality.from_json(raw.get("locality")),
            categories=tuple(Facet.from_json(f) for f in raw.get("categories") or ()),
            brands=tuple(Facet.from_json(f) for f in raw.get("brands") or ()),
            places=tuple(Place.from_json(p) for p in raw.get("places") or ()),
            neighbours=tuple(LocalityLink.from_json(l) for l in raw.get("neighbours") or ()),
        )


@dataclass(frozen=True)
class PlaceDetail:
    """One location, where it is, what is near it, and what people said."""

    country: Country = field(default_factory=Country)
    region: Region = field(default_factory=Region)
    locality: Locality = field(default_factory=Locality)
    place: Place = field(default_factory=Place)
    nearby: "tuple[PlaceLink, ...]" = ()
    reviews: Reviews = field(default_factory=Reviews)
    photos: "tuple[Photo, ...]" = ()

    @property
    def path(self) -> str:
        return place_path(
            self.country.slug, self.region.slug, self.locality.slug, self.place.brand, self.place.slug
        )

    @classmethod
    def from_json(cls, raw: Mapping[str, Any] | None) -> "PlaceDetail":
        raw = raw or {}
        return cls(
            country=Country.from_json(raw.get("country")),
            region=Region.from_json(raw.get("region")),
            locality=Locality.from_json(raw.get("locality")),
            place=Place.from_json(raw.get("place")),
            nearby=tuple(PlaceLink.from_json(p) for p in raw.get("nearby") or ()),
            reviews=Reviews.from_json(raw.get("reviews")),
            photos=tuple(Photo.from_json(p) for p in raw.get("photos") or ()),
        )
