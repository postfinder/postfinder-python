"""The controls that stop this client being turned against its caller.

There is no key to leak here: the API is keyless. What passes through instead
is what a person typed into a search box, which in an address product is
routinely their own street address, and the URLs this client builds from
whatever a caller passes in. So: the destination cannot be moved off https, a
slug cannot walk out of its path prefix, and nothing a caller supplies reaches
a header or a query unencoded.
"""

from __future__ import annotations

import json
import unittest
import urllib.error

from postfinder import DEFAULT_BASE_URL, PostFinder
from postfinder._client import _SameOriginRedirects


class Recorder:
    def __init__(self, body=None):
        self.calls = []
        self.body = body if body is not None else {"data": [], "generated_at": "now"}

    def __call__(self, method, url, headers, timeout):
        self.calls.append((method, url, headers, timeout))
        return 200, json.dumps(self.body).encode()

    @property
    def url(self):
        return self.calls[-1][1]


class TestWhereRequestsMayGo(unittest.TestCase):
    def test_the_default_is_https(self):
        self.assertTrue(DEFAULT_BASE_URL.startswith("https://"))

    def test_plaintext_http_to_a_public_host_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            PostFinder(base_url="http://api.postfinder.io")
        self.assertIn("clear", str(caught.exception))

    def test_loopback_over_http_is_allowed_for_a_test_server(self):
        for url in ("http://localhost:8080", "http://127.0.0.1:8080", "http://[::1]:8080"):
            PostFinder(base_url=url)

    def test_another_scheme_is_refused(self):
        for url in ("ftp://api.postfinder.io", "file:///etc/passwd", "gopher://x"):
            with self.assertRaises(ValueError):
                PostFinder(base_url=url)

    def test_a_relative_or_empty_base_url_is_refused(self):
        for url in ("", "api.postfinder.io", "/v1"):
            with self.assertRaises(ValueError):
                PostFinder(base_url=url)

    def test_a_base_url_carrying_credentials_is_refused(self):
        # https://user:pass@evil.example/ reads as the real host to a person
        # skimming a config file and is a different host to urllib. Nothing
        # here needs userinfo, so it is refused rather than honoured.
        with self.assertRaises(ValueError) as caught:
            PostFinder(base_url="https://api.postfinder.io:pass@evil.example")
        self.assertIn("credentials", str(caught.exception))

    def test_a_redirect_off_the_host_is_refused(self):
        handler = _SameOriginRedirects()
        req = urllib.request.Request("https://api.postfinder.io/v1/search?q=1+smith+st")

        for target in (
            "https://evil.example/v1/search?q=1+smith+st",
            "http://api.postfinder.io/v1/search?q=1+smith+st",
        ):
            with self.assertRaises(urllib.error.HTTPError):
                handler.redirect_request(req, None, 302, "Found", {}, target)

    def test_a_redirect_on_the_same_host_is_followed(self):
        handler = _SameOriginRedirects()
        req = urllib.request.Request("https://api.postfinder.io/v1/search?q=coburg")
        self.assertIsNotNone(
            handler.redirect_request(req, None, 301, "Moved", {}, "https://api.postfinder.io/v1/search?q=coburg&x=1")
        )


class TestWhatReachesTheWire(unittest.TestCase):
    def test_a_slug_cannot_walk_out_of_its_path_prefix(self):
        # The API separates its products by path prefix and the ingress routes
        # them separately, so an unencoded slug is not a cosmetic problem: it is
        # how a directory call becomes a call to something else.
        rec = Recorder(body={"data": {}})
        pf = PostFinder(transport=rec)

        pf.country("../../v1/keys")
        self.assertNotIn("/v1/keys", rec.url)
        self.assertIn("..%2F..%2Fv1%2Fkeys", rec.url)

        pf.locality("australia", "victoria", "../../../v1/addresses")
        self.assertNotIn("/v1/addresses", rec.url)

        pf.place("..%2F..")
        self.assertTrue(rec.url.startswith("https://api.postfinder.io/v1/places/"))

    def test_a_slug_cannot_smuggle_a_query_string(self):
        rec = Recorder(body={"data": {}})
        PostFinder(transport=rec).country("australia?limit=9999")
        self.assertNotIn("?", rec.url)

    def test_an_empty_slug_is_refused_rather_than_becoming_a_list_call(self):
        # /v1/countries//postcodes is not the call anybody meant, and on some
        # paths a dropped segment is a different, broader endpoint.
        rec = Recorder()
        pf = PostFinder(transport=rec)
        for call in (
            lambda: pf.country(""),
            lambda: pf.locality("australia", "", "coburg"),
            lambda: pf.place("  "),
            lambda: pf.postcodes(""),
        ):
            with self.assertRaises(ValueError):
                call()
        self.assertEqual([], rec.calls)

    def test_a_query_cannot_inject_another_parameter(self):
        rec = Recorder()
        PostFinder(transport=rec).search("coburg&limit=9999&country=x")

        self.assertIn("q=coburg%26limit%3D9999%26country%3Dx", rec.url)
        self.assertNotIn("&limit=9999", rec.url)

    def test_a_query_with_crlf_cannot_split_the_request(self):
        rec = Recorder()
        PostFinder(transport=rec).search("coburg\r\nX-Injected: 1")

        self.assertNotIn("\r", rec.url)
        self.assertNotIn("\n", rec.url)
        self.assertIn("%0D%0A", rec.url)

    def test_a_contact_with_crlf_is_refused(self):
        # contact goes into the User-Agent. A newline there is a header the
        # caller did not write.
        with self.assertRaises(ValueError):
            PostFinder(contact="https://example.com\r\nAuthorization: Bearer x")

    def test_no_credential_header_is_ever_sent(self):
        # This API takes none. A client that sent one would be teaching callers
        # to put a key where an edge cache can see it.
        rec = Recorder()
        PostFinder(transport=rec).search("coburg")
        headers = rec.calls[-1][2]

        self.assertEqual({"Accept", "User-Agent"}, set(headers))
        self.assertNotIn("Cookie", headers)


class TestWhatComesBack(unittest.TestCase):
    def test_a_body_that_is_not_an_object_does_not_crash_the_parse(self):
        for raw in (b"[1,2,3]", b'"gotcha"', b"null", b"", b"{"):
            pf = PostFinder(transport=lambda m, u, h, t, raw=raw: (200, raw))
            self.assertEqual([], pf.search("coburg"))

    def test_reads_are_bounded(self):
        # A client should not be talked into reading an unbounded body by
        # whatever answered the socket.
        from postfinder._client import _MAX_BODY

        self.assertLessEqual(_MAX_BODY, 64 << 20)
        self.assertGreater(_MAX_BODY, 8 << 20)  # a postcode index is megabytes


if __name__ == "__main__":
    unittest.main()
