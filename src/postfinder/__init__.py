"""PostFinder: post offices, parcel lockers and post boxes, as an API.

Free, keyless and cached at the edge. The directory behind postfinder.io.

    >>> from postfinder import PostFinder
    >>> pf = PostFinder()
    >>> near = pf.nearby(-37.7404, 144.9633, category="post-offices",
    ...                  country="australia")
    >>> near[0].name, near[0].distance_m
    ('Coburg Post Office', 420)

Data from OpenStreetMap (ODbL) and GeoNames (CC BY 4.0). Publishing what you
get back means carrying those credits: postfinder.io/en/legal/.
"""

from ._client import DEFAULT_BASE_URL, MIN_QUERY, PostFinder, Transport, __version__
from ._errors import BadRequest, NotFound, PostFinderError, RateLimited
from ._models import (
    CATEGORIES,
    CategoryHub,
    Country,
    CountryDetail,
    CountrySummary,
    Facet,
    Locality,
    LocalityDetail,
    LocalityLink,
    LocalitySummary,
    NearbyPlace,
    Photo,
    Place,
    PlaceDetail,
    PlaceLink,
    PostcodeDetail,
    PostcodeEntry,
    PostcodeIndex,
    Region,
    RegionDetail,
    RegionPostcodes,
    RegionSummary,
    Review,
    Reviews,
    ReviewSummary,
    SearchHit,
    locality_path,
    place_path,
)

__all__ = [
    "CATEGORIES",
    "DEFAULT_BASE_URL",
    "MIN_QUERY",
    "BadRequest",
    "CategoryHub",
    "Country",
    "CountryDetail",
    "CountrySummary",
    "Facet",
    "Locality",
    "LocalityDetail",
    "LocalityLink",
    "LocalitySummary",
    "NearbyPlace",
    "NotFound",
    "Photo",
    "Place",
    "PlaceDetail",
    "PlaceLink",
    "PostFinder",
    "PostFinderError",
    "PostcodeDetail",
    "PostcodeEntry",
    "PostcodeIndex",
    "RateLimited",
    "Region",
    "RegionDetail",
    "RegionPostcodes",
    "RegionSummary",
    "Review",
    "ReviewSummary",
    "Reviews",
    "SearchHit",
    "Transport",
    "__version__",
    "locality_path",
    "place_path",
]
