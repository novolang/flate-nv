# flate-nv

**Status: NOT IMPLEMENTED — interface only.**

Every public function below is published with its signature and its
effect row, and every body is `todo()`. Installing this package works;
calling it panics with `not implemented`.

## What this is

DEFLATE (RFC 1951) and the two containers built on it — zlib (RFC
1950) and gzip (RFC 1952) — read and written by a package that
performs nothing itself. The decoder is a feed-and-drain state
machine: you hand it whatever bytes you have, it hands back the
plaintext those bytes produced and the decoder to feed next. The
encoder takes input and returns compressed bytes, and you decide where
they go. The two container headers are typed values you can build,
parse and read on their own; CRC32 and Adler-32 are exposed because
the containers demand them; and every error names the byte offset in
the compressed stream that a person can `xxd -s` to.

It is for the program that has to read or write a compressed stream
before it can do anything else: an HTTP client honouring
`Content-Encoding`, a `.gz` log reader, a PNG decoder (every `IDAT`
chain is a zlib stream), zip-nv, and a device that has 40 KiB of RAM
and a firmware image to unpack.

```
novo pkg add flate-nv
novo pkg build
novo test
```

## The one example that will work

```novo
use inflate
use deflate
use flate

fn roundtrip(text: Str) -> Result<Bytes, FlateError>
    let packed = deflate.compress(bytes.from_str(text), GzipWrapped, flate.balanced())
    inflate.decompress(packed, GzipWrapped)
```

`compress` cannot fail — with a `FlateLevel` in hand there is nothing
left to go wrong — so only the decode returns a `Result`, and its `Ok`
means the gzip trailer's CRC32 and length both verified.

## The layer, and why

`core` — no effects at all, on a package whose whole subject is a
stream.

That is not a contradiction, it is the design. Inflating is arithmetic
over bytes the caller already holds: nothing is opened, nothing is
waited for, and the state a decoder carries between chunks is a 32 KiB
window, a bit buffer and a dozen integers. RFC 1951 § 4 caps a
back-reference at 32,768 bytes, which is what puts a hard ceiling on
that state and is why this package genuinely fits on a device rather
than merely claiming to.

The one function that meets a stream stays inside the budget by
**binding** its cost rather than spending one:

```novo
pub fn read_all<S: Read[e]>(src: S, fmt: FlateFormat) -> Result<Bytes, FlateError> [e]
```

`S: Read[e]` binds the effect parameter of the standard library's
`Read` trait and the clause uses it, so the row means *whatever the
impl behind `S` supplies*. A file charges its caller `[io]`; an
in-memory buffer charges nothing; `flate-nv` is charged neither,
because the impl that supplies the effect is declared where the host
is.

## The load-bearing interface

```novo
pub fn inflater(fmt: FlateFormat) -> Inflater
pub fn feed(d: Inflater, chunk: Bytes) -> (Inflater, Bytes)
pub fn finish(d: Inflater) -> Result<Bytes, FlateError>
```

Three calls, and every other decoding function in the package is
either a value they take, a value they return, or a convenience
written in terms of them. `feed` returns a NEW decoder rather than
mutating one because `[mutate]` is a host effect and this package has
none — which is also what makes a decoder safe to keep, fork, or feed
from two places.

A chunk may split anything: a Huffman code, a length/distance pair,
the two bytes of a zlib header, the gzip trailer between its CRC and
its length. Whatever a chunk could not finish is carried in the
decoder and completed by the next one.

**The one thing to understand about streaming decompression is that
`feed` hands back bytes it has not verified.** The checksum lives in
the trailer, so a streaming decoder cannot check as it goes and must
not pretend to; only a successful `finish` says the output was
correct. A caller who cannot tolerate that buffers until `finish`
returns, or uses `decompress`, which does.

The encoder is `push` / `flush` / `finish` rather than
`feed` / `finish`, because an encoder holds input back to find matches
in it: `push` usually returns nothing, `flush` is how a caller who
needs bytes on the wire now gets them at a cost in ratio, and `finish`
writes the final block and the trailer and is not optional.

## The reference implementation, and what is specification

zlib is the reference implementation and its corpus is the oracle. The
distinction the plan asks for, because it decides what a test may
assert:

**Specification, and binding on this package**

- The DEFLATE bit stream: block types, the fixed and dynamic Huffman
  alphabets, the length and distance codes, the 32,768-byte window
  cap, BFINAL (RFC 1951).
- The zlib container: CM = 8, the window bits, FDICT, the requirement
  that the two header bytes read big-endian be a multiple of 31, and
  the BIG-endian Adler-32 trailer (RFC 1950).
- The gzip container: the `1f 8b` magic, CM = 8, the flag bits and the
  optional fields they gate, and the LITTLE-endian CRC32 + length
  trailer (RFC 1952). The two endiannesses disagree on purpose and
  neither is negotiable.
- Adler-32's modulus and seed, and CRC32's reflected IEEE polynomial.

**zlib's own choices, which this package follows and a test may not
treat as correctness**

- That compression LEVELS exist at all, and that they run 0–9 with 6
  as the default. RFC 1951 says nothing about a level; a conforming
  encoder may emit any valid stream at any of them.
- `FlateStrategy` entirely — filtered, Huffman-only, RLE, fixed. All
  four are zlib inventions, and every one produces a stream any
  decoder reads.
- Where blocks are split, when a dynamic table beats a fixed one, how
  far the match search looks. This is where an encoder's output size
  comes from and none of it is specified.

So the correctness condition is **zlib inflates what this deflates,
and this inflates what zlib deflates**. Byte-for-byte equality with
zlib's output at the default level is an aspiration for the
implementation lane, not a condition on it, and a test that asserted
it would be a test of this encoder's block-splitting heuristics rather
than of DEFLATE.

**Deliberately not ported:** preset dictionaries (the interface
reports `ZlibDictionaryRequired` with the id and stops there),
`inflateBack`, `gzread`-style file helpers — a `core` package has no
files — and gzip's FEXTRA subfield registry, which belongs where the
application that defined a subfield is.

## Two places the sans-IO rule shows through

Worth knowing before you meet them:

- **`gzip.header()` defaults `mtime` to 0 and the OS byte to 255.**
  gzip(1) writes the real modification time and the real platform;
  this package cannot, because reading a clock is `[time]` and `core`
  has none. A caller who wants the real time passes it to
  `gzip.with_mtime`.
- **`gzip.with_name` does not sanitise the name.** RFC 1952 § 2.3.1
  says the field is a base name with no directory, and a decompressor
  that honoured a path in it would have a directory-traversal hole.
  This package neither enforces nor strips, because it does not know
  what a path looks like on your machine and has no filesystem to
  check against. **A caller extracting to disk must sanitise what
  `inflate.gzip_header` returned before using it as a file name.**

There is also no default size limit. A DEFLATE stream can expand
roughly a thousandfold, so a decoder with no bound will one day be
handed a bomb — but the right bound is your memory budget rather than
this package's opinion, so the default is unbounded and
`inflate.with_limit` is how you state one.

## Status

Every function is `todo()`. `novo test` runs the API suite, and every
assertion in it reaches `not implemented: flate-nv.<fn>` — which is
the expected result until the bodies land, and is what makes the suite
a description of the interface rather than of nothing.
`novo test --isolate` is the readable form: one verdict per test,
naming the function it stopped at.

| module | public types | functions | implemented |
| --- | --- | --- | --- |
| `flate` | 3 | 8 | no |
| `flatecheck` | 2 | 8 | no |
| `flateerror` | 1 | 2 | no |
| `inflate` | 1 | 14 | no |
| `deflate` | 1 | 13 | no |
| `gzip` | 1 | 12 | no |
| `zlib` | 1 | 9 | no |
| **total** | **10** | **66** | **no** |
