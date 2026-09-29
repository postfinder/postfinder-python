"""The PostFinder client, tested against the shape the API actually sends.

unittest rather than pytest so the suite runs with nothing installed: the
library has no dependencies, and a test suite that needs one is a worse first
impression than no test suite. pytest runs these too.

The fixtures below are the envelopes internal/domain writes, field for field.
"""

from __future__ import annotations

import json
import unittest

from postfinder import (
    CATEGORIES,
    BadRequest,
    NotFound,
    PostFinder,
    PostFinderError,
    RateLimited,
)

SEARCH = {
    "data": [
        {
            "kind": "locality",
            "slug": "coburg",
            "name": "Coburg",
            "country": "australia",
            "region": "victoria",
            "postcode": "3058",
            "place_count": 14,
            "state": "VIC",
            "lat": -37.7404,
            "lng": 144.9633,
            "score": 0.91,
        },
        {
            "kind": "place",
            "slug": "coburg-post-office",
            "name": "Coburg Post Office",
            "country": "australia",
            "region": "victoria",
            "locality": "coburg",
            "postcode": "3058",
            "score": 0.74,
        },
    ],
    "generated_at": "2026-09-29T02:11:00Z",
}

NEARBY = {
    "data": [
        {
            "public_id": "k7m2p9x4",
            "slug": "coburg-post-office",
            "name": "Coburg Post Office",
            "brand": "australia-post",
            "category": "post-offices",
            "address": "484 Sydney Rd",
            "lat": -37.7412,
            "lng": 144.9645,
            "hours": {"mon": "9:00-17:00"},
            "country": "australia",
            "region": "victoria",
            "locality": "coburg",
            "distance_km": 0.42,
        }
    ],
    "generated_at": "2026-09-29T02:11:00Z",
}

PLACE = {
    "data": {
        "country": {"iso2": "AU", "slug": "australia", "name": "Australia"},
        "region": {"slug": "victoria", "code": "VIC", "name": "Victoria"},
        "locality": {"slug": "coburg", "name": "Coburg", "postcode": "3058", "place_count": 14},
        "place": {
            "public_id": "k7m2p9x4",
            "slug": "coburg-post-office",
            "name": "Coburg Post Office",
            "brand": "australia-post",
            "category": "post-offices",
            "lat": -37.7412,
            "lng": 144.9645,
        },
        "nearby": [
            {
                "public_id": "q3f8t1v6",
                "slug": "coburg-north-lpo",
                "name": "Coburg North LPO",
                "brand": "australia-post",
                "category": "post-offices",
                "country": "australia",
                "region": "victoria",
                "locality": "coburg-north",
                "distance_km": 1.8,
            }
        ],
        "reviews": {"summary": {"count": 2, "average": 4.5, "last_as_listed_at": None}, "recent": []},
        "photos": [],
    },
    "generated_at": "2026-09-29T02:11:00Z",
}

POSTCODES = {
    "data": {
        "country": {"iso2": "AU", "slug": "australia", "name": "Australia"},
        "total": 3,
        "regions": [
            {
                "region": {"slug": "victoria", "code": "VIC", "name": "Victoria"},
                "entries": [
                    {"postcode": "3058", "slug": "coburg", "name": "Coburg", "place_count": 14},
                    {"postcode": "3058", "slug": "merlynston", "name": "Merlynston", "place_count": 1},
                ],
            },
            {
                "region": {"slug": "new-south-wales", "code": "NSW", "name": "New South Wales"},
                "entries": [
                    {"postcode": "2044", "slug": "sydenham", "name": "Sydenham", "place_count": 3}
                ],
            },
        ],
    },
    "generated_at": "2026-09-29T02:11:00Z",
}

POSTCODE = {
    "data": {
        "country": {"iso2": "AU", "slug": "australia", "name": "Australia"},
        "region": {"slug": "victoria", "code": "VIC", "name": "Victoria"},
        "postcode": "3058",
        "total": 16,
        "localities": [
            {
                "country": "australia",
                "region": "victoria",
                "slug": "coburg",
                "name": "Coburg",
                "place_count": 14,
                "distance_km": 0.0,
            }
        ],
    },
    "generated_at": "2026-09-29T02:11:00Z",
}

LOCALITY = {
    "data": {
        "country": {"iso2": "AU", "slug": "australia", "name": "Australia"},
        "region": {"slug": "victoria", "code": "VIC", "name": "Victoria"},
        "locality": {"slug": "coburg", "name": "Coburg", "postcode": "3058", "place_count": 14},
        "categories": [{"key": "post-offices", "count": 2}, {"key": "post-boxes", "count": 12}],
        "brands": [{"key": "australia-post", "count": 14}],
        "places": [
            {
                "public_id": "k7m2p9x4",
                "slug": "coburg-post-office",
                "name": "Coburg Post Office",
                "brand": "australia-post",
                "category": "post-offices",
                "lat": -37.7412,
                "lng": 144.9645,
            }
        ],
        "neighbours": [],
    },
    "generated_at": "2026-09-29T02:11:00Z",
}

COUNTRIES = {
    "data": [
        {
            "iso2": "AU",
            "slug": "australia",
            "name": "Australia",
            "region_count": 8,
            "locality_count": 15304,
            "place_count": 40122,
        }
    ],
    "generated_at": "2026-09-29T02:11:00Z",
}

COUNTRY = {
    "data": {
        "country": {"iso2": "AU", "slug": "australia", "name": "Australia"},
        "regions": [
            {"slug": "victoria", "code": "VIC", "name": "Victoria", "locality_count": 3021, "place_count": 9120}
        ],
    },
    "generated_at": "2026-09-29T02:11:00Z",
}

REGION = {
    "data": {
        "country": {"iso2": "AU", "slug": "australia", "name": "Australia"},
        "region": {"slug": "victoria", "code": "VIC", "name": "Victoria"},
        "localities": [{"slug": "coburg", "name": "Coburg", "postcode": "3058", "place_count": 14}],
        "locality_total": 3021,
    },
    "generated_at": "2026-09-29T02:11:00Z",
}

CATEGORY = {
    "data": {
        "country": {"iso2": "AU", "slug": "australia", "name": "Australia"},
        "category": "parcel-lockers",
        "total": 621,
        "regions": [
            {"slug": "victoria", "code": "VIC", "name": "Victoria", "locality_count": 0, "place_count": 180}
        ],
        "localities": [
            {
                "country": "australia",
                "region": "victoria",
                "slug": "coburg",
                "name": "Coburg",
                "place_count": 4,
                "distance_km": 0.0,
            }
        ],
    },
    "generated_at": "2026-09-29T02:11:00Z",
}

PROBLEM = {"type": "about:blank", "title": "place not found", "status": 404, "detail": ""}


class Recorder:
    """A transport that records the request and returns a canned answer."""

    def __init__(self, status=200, body=None):
        self.status = status
        self.body = body if body is not None else SEARCH
        self.calls = []

    def __call__(self, method, url, headers, timeout):
        self.calls.append((method, url, headers, timeout))
        return self.status, json.dumps(self.body).encode()

    @property
    def url(self):
        return self.calls[-1][1]


def client(recorder):
    return PostFinder(transport=recorder)


class TestSearch(unittest.TestCase):
    def test_returns_typed_hits(self):
        pf = client(Recorder(body=SEARCH))
        hits = pf.search("coburg")

        self.assertEqual(2, len(hits))
        self.assertEqual("locality", hits[0].kind)
        self.assertEqual("Coburg", hits[0].name)
        self.assertEqual("3058", hits[0].postcode)
        self.assertEqual(14, hits[0].place_count)
        self.assertAlmostEqual(-37.7404, hits[0].lat)
        self.assertEqual("place", hits[1].kind)
        self.assertEqual("coburg", hits[1].locality)
        # A place hit has no coordinate in a search row, and None says so
        # rather than 0.0, which is a real place in the Gulf of Guinea.
        self.assertIsNone(hits[1].lat)

    def test_hit_knows_its_path_on_the_website(self):
        # The reason every row carries country, region and slug: a caller
        # builds the link without a second request.
        pf = client(Recorder(body=SEARCH))
        hits = pf.search("coburg")

        self.assertEqual("/en/australia/victoria/coburg/", hits[0].path)
        # A place row carries no brand key, and the place page's path has a
        # brand segment in it. So a place hit links to its suburb, which is
        # what the API's own MCP tool does with the same row. place() returns
        # the exact path.
        self.assertEqual("/en/australia/victoria/coburg/", hits[1].path)

    def test_sends_the_query_and_the_limit(self):
        rec = Recorder()
        client(rec).search("coburg", limit=5)

        self.assertIn("q=coburg", rec.url)
        self.assertIn("limit=5", rec.url)
        self.assertTrue(rec.url.startswith("https://api.postfinder.io/v1/search?"))

    def test_one_character_costs_no_request(self):
        # The service answers an empty list below two characters. Asking it to
        # say so spends a request, a DNS lookup and a TLS handshake for an
        # answer that is known here.
        rec = Recorder()
        self.assertEqual([], client(rec).search("c"))
        self.assertEqual([], client(rec).search("  "))
        self.assertEqual([], rec.calls)

    def test_a_query_is_encoded_not_interpolated(self):
        rec = Recorder()
        client(rec).search("coburg & brunswick", limit=5)

        self.assertIn("q=coburg+%26+brunswick", rec.url)
        # One limit, the caller's. A query that could smuggle a second
        # parameter could also smuggle a different endpoint's.
        self.assertEqual(1, rec.url.count("limit="))


class TestNearby(unittest.TestCase):
    def test_returns_places_with_a_distance(self):
        pf = client(Recorder(body=NEARBY))
        found = pf.nearby(-37.7404, 144.9633, category="post-offices", country="australia")

        self.assertEqual(1, len(found))
        self.assertEqual("Coburg Post Office", found[0].name)
        self.assertAlmostEqual(0.42, found[0].distance_km)
        self.assertEqual(420, found[0].distance_m)
        self.assertEqual("484 Sydney Rd", found[0].address)
        self.assertEqual({"mon": "9:00-17:00"}, found[0].hours)
        self.assertEqual(
            "/en/australia/victoria/coburg/australia-post/coburg-post-office/",
            found[0].path,
        )

    def test_sends_every_parameter_the_endpoint_requires(self):
        rec = Recorder(body=NEARBY)
        client(rec).nearby(-37.7404, 144.9633, category="post-offices", country="australia")

        for part in ("lat=-37.7404", "lng=144.9633", "category=post-offices", "country=australia"):
            self.assertIn(part, rec.url)

    def test_an_unknown_category_is_refused_before_the_request(self):
        # The service answers 400. It can be known here, and a ValueError
        # naming the six categories is a better error than a problem document.
        rec = Recorder(body=NEARBY)
        with self.assertRaises(ValueError) as caught:
            client(rec).nearby(-37.7, 144.9, category="postboxes", country="australia")

        self.assertIn("post-boxes", str(caught.exception))
        self.assertEqual([], rec.calls)

    def test_a_coordinate_off_the_globe_is_refused_before_the_request(self):
        rec = Recorder(body=NEARBY)
        with self.assertRaises(ValueError):
            client(rec).nearby(-91.0, 144.9, category="post-offices", country="australia")
        with self.assertRaises(ValueError):
            client(rec).nearby(-37.7, 181.0, category="post-offices", country="australia")
        self.assertEqual([], rec.calls)

    def test_the_categories_are_published(self):
        self.assertEqual(
            (
                "post-offices",
                "post-boxes",
                "express-post-boxes",
                "parcel-lockers",
                "drop-off-points",
                "collection-points",
            ),
            CATEGORIES,
        )


class TestPlace(unittest.TestCase):
    def test_returns_the_place_and_where_it_is(self):
        pf = client(Recorder(body=PLACE))
        detail = pf.place("k7m2p9x4")

        self.assertEqual("Coburg Post Office", detail.place.name)
        self.assertEqual("Coburg", detail.locality.name)
        self.assertEqual("VIC", detail.region.code)
        self.assertEqual("AU", detail.country.iso2)
        self.assertEqual(1, len(detail.nearby))
        self.assertEqual("Coburg North LPO", detail.nearby[0].name)
        self.assertEqual(2, detail.reviews.summary.count)
        self.assertEqual(4.5, detail.reviews.summary.average)
        self.assertEqual(
            "/en/australia/victoria/coburg/australia-post/coburg-post-office/",
            detail.path,
        )

    def test_an_unknown_id_raises_not_found(self):
        pf = client(Recorder(status=404, body=PROBLEM))
        with self.assertRaises(NotFound) as caught:
            pf.place("nosuchid")

        self.assertEqual(404, caught.exception.status)
        self.assertEqual("place not found", caught.exception.title)
        self.assertIsInstance(caught.exception, PostFinderError)


class TestDirectory(unittest.TestCase):
    def test_countries(self):
        pf = client(Recorder(body=COUNTRIES))
        countries = pf.countries()

        self.assertEqual("Australia", countries[0].name)
        self.assertEqual(40122, countries[0].place_count)
        self.assertEqual("/en/australia/", countries[0].path)

    def test_country(self):
        rec = Recorder(body=COUNTRY)
        detail = client(rec).country("australia")

        self.assertEqual("https://api.postfinder.io/v1/countries/australia", rec.url)
        self.assertEqual("Victoria", detail.regions[0].name)
        self.assertEqual(9120, detail.regions[0].place_count)

    def test_region_pages_through_its_localities(self):
        rec = Recorder(body=REGION)
        detail = client(rec).region("australia", "victoria", limit=1, offset=200)

        self.assertIn("/v1/countries/australia/regions/victoria?", rec.url)
        self.assertIn("limit=1", rec.url)
        self.assertIn("offset=200", rec.url)
        self.assertEqual(3021, detail.locality_total)
        self.assertEqual("Coburg", detail.localities[0].name)

    def test_locality(self):
        rec = Recorder(body=LOCALITY)
        detail = client(rec).locality("australia", "victoria", "coburg")

        self.assertEqual(
            "https://api.postfinder.io/v1/localities/australia/victoria/coburg", rec.url
        )
        self.assertEqual(14, detail.locality.place_count)
        self.assertEqual("Coburg Post Office", detail.places[0].name)
        self.assertEqual(12, detail.count_of("post-boxes"))
        self.assertEqual(0, detail.count_of("parcel-lockers"))

    def test_category_hub(self):
        rec = Recorder(body=CATEGORY)
        hub = client(rec).category("australia", "parcel-lockers", region="victoria")

        self.assertIn("/v1/countries/australia/categories/parcel-lockers?", rec.url)
        self.assertIn("region=victoria", rec.url)
        self.assertEqual(621, hub.total)
        self.assertEqual("Coburg", hub.localities[0].name)


class TestPostcodes(unittest.TestCase):
    def test_index_groups_by_region(self):
        pf = client(Recorder(body=POSTCODES))
        index = pf.postcodes("australia")

        self.assertEqual(3, index.total)
        self.assertEqual("Victoria", index.regions[0].region.name)
        self.assertEqual("Coburg", index.regions[0].entries[0].name)

    def test_index_looks_a_postcode_up_without_rescanning(self):
        # The whole country arrives in one response and is meant to be kept.
        # Reading it should not mean walking every region for every lookup, so
        # the index builds its map once on first use.
        pf = client(Recorder(body=POSTCODES))
        index = pf.postcodes("australia")

        self.assertEqual(
            ["Coburg", "Merlynston"], [e.name for e in index.suburbs_in("3058")]
        )
        self.assertEqual(["Sydenham"], [e.name for e in index.suburbs_in("2044")])
        # Empty tuple, like every other list on a parsed answer: what comes
        # back is immutable, so a cached index cannot be edited by a caller.
        self.assertEqual((), index.suburbs_in("9999"))
        # Same objects back on a second call: the map is built, not rebuilt.
        self.assertIs(index.suburbs_in("3058")[0], index.suburbs_in("3058")[0])

    def test_one_postcode_lists_every_suburb_it_covers(self):
        rec = Recorder(body=POSTCODE)
        detail = client(rec).postcode("australia", "3058")

        self.assertEqual(
            "https://api.postfinder.io/v1/countries/australia/postcodes/3058", rec.url
        )
        self.assertEqual("3058", detail.postcode)
        self.assertEqual(16, detail.total)
        self.assertEqual("Coburg", detail.localities[0].name)
        self.assertEqual("/en/australia/victoria/coburg/", detail.localities[0].path)

    def test_a_postcode_that_is_not_digits_is_refused_before_the_request(self):
        rec = Recorder(body=POSTCODE)
        with self.assertRaises(ValueError):
            client(rec).postcode("australia", "SW1A 1AA")
        self.assertEqual([], rec.calls)


class TestErrors(unittest.TestCase):
    def test_400_is_its_own_class(self):
        pf = client(Recorder(status=400, body={"title": "invalid nearby search", "detail": "Choose a category."}))
        with self.assertRaises(BadRequest) as caught:
            pf.search("coburg")
        self.assertEqual("invalid nearby search: Choose a category.", str(caught.exception).split(" ", 1)[1])

    def test_429_carries_what_to_wait(self):
        rec = Recorder(status=429, body={"title": "too many requests"})
        pf = PostFinder(transport=lambda m, u, h, t: (429, json.dumps({"title": "too many requests"}).encode()))
        with self.assertRaises(RateLimited) as caught:
            pf.search("coburg")
        self.assertEqual(429, caught.exception.status)

    def test_a_body_that_is_not_json_still_raises_with_the_status(self):
        pf = PostFinder(transport=lambda m, u, h, t: (502, b"<html>bad gateway</html>"))
        with self.assertRaises(PostFinderError) as caught:
            pf.search("coburg")
        self.assertEqual(502, caught.exception.status)

    def test_an_unknown_field_is_ignored_rather_than_fatal(self):
        # The service may add a field before this library knows the name.
        body = {"data": [dict(SEARCH["data"][0], something_new="x")], "generated_at": "now"}
        pf = client(Recorder(body=body))
        self.assertEqual("Coburg", pf.search("coburg")[0].name)


class TestRequests(unittest.TestCase):
    def test_sends_no_credential_and_says_who_it_is(self):
        rec = Recorder()
        client(rec).search("coburg")
        _, _, headers, _ = rec.calls[-1]

        self.assertNotIn("Authorization", headers)
        self.assertEqual("application/json", headers["Accept"])
        self.assertTrue(headers["User-Agent"].startswith("postfinder-python/"))

    def test_a_contact_is_added_to_the_user_agent_when_given(self):
        # The API asks callers doing more than a thousand a month to say what
        # they are building. A contactable User-Agent is how that conversation
        # starts before a rate limit does.
        rec = Recorder()
        PostFinder(contact="https://example.com/bot", transport=rec).search("coburg")
        self.assertIn("+https://example.com/bot", rec.calls[-1][2]["User-Agent"])

    def test_the_timeout_reaches_the_transport(self):
        rec = Recorder()
        PostFinder(timeout=2.5, transport=rec).search("coburg")
        self.assertEqual(2.5, rec.calls[-1][3])


if __name__ == "__main__":
    unittest.main()
