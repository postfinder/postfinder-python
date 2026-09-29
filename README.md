# postfinder

**Post offices, parcel lockers and post boxes, as an API.** Ask what is nearest
a coordinate, look up what a postcode covers, or read a suburb's locations.

- Free and keyless. No account, no quota to buy, nothing to configure
- Answers are cached at the edge, so a repeated question is fast and costs
  nobody anything
- Every row knows the page it belongs to on postfinder.io, so linking out takes
  no second request
- No dependencies

```sh
pip install postfinder
```

## Quick start

```python
from postfinder import PostFinder

pf = PostFinder()

for p in pf.nearby(-37.7404, 144.9633, category="post-offices", country="australia"):
    print(p.name, p.address, f"{p.distance_m} m")
```

```
Coburg Post Office 484 Sydney Rd 420 m
Coburg North LPO 12 Elizabeth St 1800 m
```

Nearest first, within 50km, at most 30 rows. That is the question "where do I
post this", which is a different question from "list every post box in
Victoria".

## The six categories

```python
from postfinder import CATEGORIES   # what nearby() accepts
```

`post-offices`, `post-boxes`, `express-post-boxes`, `parcel-lockers`,
`drop-off-points`, `collection-points`.

A name that is not one of those raises `ValueError` before a request goes out,
rather than spending a round trip to be told 400.

## Typeahead

```python
for hit in pf.search("coburg"):
    print(hit.kind, hit.name, hit.postcode, hit.path)
```

```
locality Coburg 3058 /en/australia/victoria/coburg/
place Coburg Post Office 3058 /en/australia/victoria/coburg/
```

Two characters minimum: below that the client returns an empty list without
asking, which is what the service answers anyway. Debounce by at least 150ms.
Firing on every keystroke spends bandwidth for no better answer.

## Postcodes

A postcode is not a suburb. 3058 is Coburg, Coburg North and Merlynston, and an
address in any of them is written with the same four digits.

```python
detail = pf.postcode("australia", "3058")
for suburb in detail.localities:
    print(suburb.name, suburb.place_count, suburb.path)
```

The whole country comes in one response, and it is meant to be kept:

```python
index = pf.postcodes("australia")        # one request
index.suburbs_in("3058")                 # no request, and no rescan
index.suburbs_in("2044")
```

`suburbs_in` builds its map on first use and keeps it, so resolving a column of
ten thousand postcodes is one pass over the index rather than ten thousand walks
through every state.

## A location, and a suburb

```python
place = pf.place("k7m2p9x4")
print(place.place.name, place.locality.name, place.path)
print(place.reviews.summary.count, place.reviews.summary.average)

suburb = pf.locality("australia", "victoria", "coburg")
print(suburb.locality.place_count, suburb.count_of("parcel-lockers"))
for p in suburb.places:
    print(p.name, suburb.path_of(p))
```

A place's public id is permanent. It is minted once and never derived from a
source record, so a feed that renumbers its rows does not change it. Store the
id, not the name or the path.

## Browsing

```python
pf.countries()                                   # every country with pages
pf.country("australia")                          # its states
pf.region("australia", "victoria", limit=100)    # its localities, a page at a time
pf.category("australia", "parcel-lockers")       # counts per state, busiest suburbs
```

## Errors

```python
from postfinder import NotFound, BadRequest, RateLimited, PostFinderError

try:
    pf.place(stored_id)
except NotFound:
    ...     # retired, or never there
```

`NotFound` is ordinary rather than a failure: a suburb with no locations has no
page, and a location that closed is retired. Every error carries the `status`,
`title` and `detail` the service sent, because that is the part that says what to
do about it.

## Being a good citizen

The API is free and asks for care in return: around a thousand requests a month
from one address, results kept rather than re-fetched, typing debounced. If you
need more than that, say what you are building at
[postfinder.io/en/contact/](https://postfinder.io/en/contact/).

Introduce yourself and it is easier to help you before a rate limit does:

```python
pf = PostFinder(contact="https://example.com/about-our-bot")
```

## Attribution

Locations come from OpenStreetMap (ODbL), localities and postcodes from GeoNames
(CC BY 4.0). If you publish what you get back, you carry those credits with it.
The [sources page](https://postfinder.io/en/legal/) names each one.

## Also available

| | |
|---|---|
| JavaScript and TypeScript | [`@postfinder/client`](https://www.npmjs.com/package/@postfinder/client) |
| React | [`@postfinder/react`](https://www.npmjs.com/package/@postfinder/react) |
| Vue | [`@postfinder/vue`](https://www.npmjs.com/package/@postfinder/vue) |
| Go | [`postfinder-go`](https://github.com/postfinder/postfinder-go) |

## Licence

MIT.
