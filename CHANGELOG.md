# Changelog

## 0.1.0

First release.

- `search`, `nearby`, `place`, `countries`, `country`, `region`, `locality`,
  `category`, `postcodes` and `postcode`, covering the free read only surface of
  api.postfinder.io.
- Every row that can build the path to its own page on postfinder.io does.
- `PostcodeIndex.suburbs_in` answers from an index already fetched, building its
  map once rather than walking every region per lookup.
- No dependencies.
