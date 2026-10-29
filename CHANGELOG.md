# Changelog

All notable changes to flate-nv are recorded here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
package follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
with the pre-1.0 rule that a breaking change bumps the MINOR number.

## 0.1.0 — 2026-10-29

First implementation of the interface published as 0.0.4. Every function has a body, the package is `experimental`, and the floor is toolchain 0.22.0.

### Added

- The decoder reads stored, fixed and dynamic blocks in raw, zlib and gzip form, across chunk boundaries of any size, with a 32 KiB window, a size limit, a strict mode and the checksum and length checks of both containers.
- The encoder writes stored, fixed and dynamic blocks from a hash-chain search with lazy matching, at levels 0 to 9 and under all five strategies, with `flush` as a sync flush.
- The tests carry streams written by CPython's zlib and gzip modules at levels 0, 1, 6 and 9 (`tests/vectors.py` regenerates them), streams assembled to be wrong in one way each, and round trips through every level, container and strategy. Line coverage of `src/` is 100%.

### Changed

- The fields of `Inflater` and `Deflater` gained the state the implementation needs (`pending`, `final_block`, `stored_left`, `lit_code`, `dist_code` on the decoder; `window` on the encoder), and the comments on `window`, `window_at`, `bit_buf` and `bit_count` say how they are used. The structs are not meant to be built or read by a caller, and no function signature changed.
- `flateerror.is_corrupt` is false for `TruncatedStream` and `SourceFailed` and true for every other reason, as its documentation says.

### Known

- A dynamic block header that declares more than 286 literal and length codes or more than 30 distance codes is reported as `BadHuffmanCode`; `FlateError` has no variant for it.
- A preset dictionary is reported with `ZlibDictionaryRequired` and not supported. `deflate.with_zlib_header` with a dictionary identifier writes the identifier and compresses without a dictionary.

## 0.0.4 — 2026-10-25

A file that names a sibling module's type, function or constant has the `use` line for that module (E2033, E2003), and the two signature illustrations in the README are fenced as illustrations.  No signature changed.

## 0.0.3 — 2026-09-12

### Changed — The README is rewritten in plain technical-writer prose; no signature changed.

## 0.0.2 — 2026-09-10

- **Toolchain floor is 0.8.9**: the bodies and signatures use what 0.8.9 added (`todo()`, a bound effect parameter, the four layers), and the manifest says so instead of letting an older toolchain fail on an undefined function.  No signature changed.

## [0.0.1] — 2026-09-09

**The interface, published before anyone implements it.** Every public
type and function carries its full signature, its effect row and its
doc comment; every body is `todo()`; the release is recorded
`implemented = false`.

### Added

- `flate` — the two values every other module takes. `FlateFormat`
  says which container wraps the bit stream (raw DEFLATE, zlib,
  gzip); `FlateLevel` makes zlib's 0–9 a value with a constructor per
  intent — `stored`, `fastest`, `balanced`, `smallest` — and one
  checked escape, `level(n)`, for the caller who genuinely has a
  number. `FlateStrategy` carries zlib's four block-choice hints.
- `inflate` — the feed-and-drain decoder, which is this package's
  load-bearing interface. `feed` takes a chunk and returns the decoder
  to feed next plus the plaintext those bytes produced; `finish` is
  end of stream and is where the container's checksum is verified. A
  chunk may split a Huffman code, a length/distance pair, or a trailer
  between its CRC and its length. `read_all<S: Read[e]>` is the same
  machine with the pump inside it, charged whatever the caller's
  stream costs (SPEC § 5.6); `decompress` is the whole buffer in one
  call, and unlike the streaming form its `Ok` means the output
  verified. `with_limit` is how a caller bounds a decompression bomb.
- `deflate` — the encoder, as `push` / `flush` / `finish` rather than
  `feed` / `finish`: an encoder holds input back to find matches in
  it, so `push` usually emits nothing, `flush` is what a protocol
  boundary needs and costs ratio, and `finish` writes the final block
  and the trailer and is not optional.
- `gzip` — RFC 1952's header as a typed value with every field named,
  built by seven `with_*` builders, parsed from bytes with the length
  it consumed, and emitted with the flag byte reconstructed from what
  is present. Plus the eight-byte little-endian trailer, both ways.
- `zlib` — RFC 1950's two header bytes as a value whose 31-multiple
  check digit is computed on emit and verified on parse, so no caller
  can hold a header with a wrong one. Plus the four-byte BIG-endian
  Adler-32 trailer, both ways.
- `flatecheck` — CRC32 (reflected IEEE) and Adler-32 as rolling
  values, because the two containers demand them and because zip-nv
  needs exactly this CRC32.
- `flateerror` — seventeen reasons, each carrying the byte offset into
  the compressed stream that a person can `xxd -s` to, or `-1` where
  there is no such place. `is_corrupt` answers the one question a
  caller deciding whether to retry actually has.

### Known

- `novo test` is red, and that is the release's expected state: every
  assertion in the API suite reaches `not implemented: flate-nv.<fn>`.
  Run it with `--isolate` for one verdict per test naming the function
  it stopped at.
- Preset dictionaries are reported (`ZlibDictionaryRequired`, with the
  dictionary's Adler-32) and not supported. The interface names the
  case so a caller that has the dictionary can detect it.
- There is no default output bound. `inflate.with_limit` is how a
  caller states one; the README says why the default is unbounded.
