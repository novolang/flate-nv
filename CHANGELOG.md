# Changelog

All notable changes to flate-nv are recorded here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
package follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
with the pre-1.0 rule that a breaking change bumps the MINOR number.

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
