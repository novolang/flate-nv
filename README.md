# flate-nv

DEFLATE is a lossless compression format, specified in
[RFC 1951](https://www.rfc-editor.org/rfc/rfc1951). Two containers are built on
it: zlib ([RFC 1950](https://www.rfc-editor.org/rfc/rfc1950)) and gzip
([RFC 1952](https://www.rfc-editor.org/rfc/rfc1952)). This package reads and
writes all three in novo-lang, and performs no input or output itself.

It is for a program that has to read or write a compressed stream before it can
do anything else: an HTTP client honouring `Content-Encoding`, a `.gz` log
reader, a PNG decoder — every `IDAT` chain is a zlib stream — a ZIP reader, or a
device with 40 KiB of RAM and a firmware image to unpack.

## What DEFLATE is

DEFLATE compresses in two steps. First it replaces repeated stretches of the
input with *back-references*: a length and a distance saying "copy this many
bytes from this far back". Then it encodes the literals and the back-references
with *Huffman codes*, which give common symbols shorter bit patterns.

A DEFLATE stream is a sequence of blocks, each with a three-bit header. A block
is stored (uncompressed), Huffman-coded with a fixed table the specification
writes down, or Huffman-coded with a table the block itself carries. The last
block is marked.

A back-reference reaches at most 32768 bytes back (RFC 1951 section 4). That
limit is what bounds a decoder's memory: the state carried between chunks is a
32 KiB window, a bit buffer and a dozen integers, and nothing else.

The two containers wrap that stream with a header and a checksum trailer.

| | zlib (RFC 1950) | gzip (RFC 1952) |
| --- | --- | --- |
| Header | 2 bytes | 10 bytes plus optional fields |
| Magic | none; the two header bytes read big-endian are a multiple of 31 | `1f 8b` |
| Checksum | Adler-32 | CRC32 |
| Trailer byte order | big-endian | little-endian |
| Trailer also carries | — | the uncompressed length, modulo 2³² |

The two byte orders disagree on purpose and neither is negotiable.

## Install

```
novo pkg add flate-nv
```

## Example

```novo
use inflate
use deflate
use flate

fn roundtrip(text: Str) -> Result<Bytes, FlateError>
    let packed = deflate.compress(bytes.from_str(text), GzipWrapped, flate.balanced())
    inflate.decompress(packed, GzipWrapped)
```

`compress` cannot fail: with a `FlateLevel` in hand there is nothing left to go
wrong. Only the decode returns a `Result`, and its `Ok` means the gzip trailer's
CRC32 and length both verified.

Build and test with:

```
novo pkg build
novo test
```

`novo test tests` runs every suite. The decoder suite reads streams that
CPython's `zlib` and `gzip` modules wrote at levels 0, 1, 6 and 9, and
`tests/vectors.py` regenerates them.

## What the package contains

| Module | Contents |
| --- | --- |
| `flate` | The values shared by both directions: `FlateFormat` (raw, zlib or gzip), `FlateLevel` with its four named settings, and `FlateStrategy`. |
| `inflate` | Decompression: the `Inflater` state machine with `feed` and `finish`, the one-shot `decompress`, `read_all` over a stream the caller supplies, and the size limit. |
| `deflate` | Compression: the `Deflater` with `push`, `flush` and `finish`, and the one-shot `compress`. |
| `gzip` | The gzip header and trailer as values: build one, parse one, read its fields. |
| `zlib` | The same for the zlib header and trailer. |
| `flatecheck` | CRC32 and Adler-32, each as a running value and as a one-shot over a buffer. The containers demand them, so they are public. |
| `flateerror` | `FlateError`, its message, and the two questions `offset_of` and `is_corrupt`. |

Ten public types and 66 public functions. No function in this package opens a
file, reads a clock or waits for anything.

The one function that meets a stream is `inflate.read_all`, and it charges its
caller rather than declaring an effect of its own:

```novo ignore
pub fn read_all<S: Read[e]>(src: S, fmt: FlateFormat) -> Result<Bytes, FlateError> [e]
```

A file charges `[io]`; an in-memory buffer charges nothing.

## How to choose an entry point

**Use `inflate.decompress` and `deflate.compress` when the whole input is in
memory.** Two calls, and `decompress` verifies the trailer before it returns.

**Use `inflate.inflater`, `feed` and `finish` when the input arrives in
pieces.**

```novo ignore
pub fn inflater(fmt: FlateFormat) -> Inflater
pub fn feed(d: Inflater, chunk: Bytes) -> (Inflater, Bytes)
pub fn finish(d: Inflater) -> Result<Bytes, FlateError>
```

`feed` returns a new decoder rather than modifying one, which is what makes a
decoder safe to keep, copy, or feed from two places.

**Use `deflate.deflater`, `push`, `flush` and `finish` to compress in pieces.**
The encoder is three calls rather than two because it holds input back to find
matches in it. `push` usually returns nothing. `flush` is how a caller who needs
bytes on the wire now gets them, at a cost in compression ratio. `finish` writes
the final block and the trailer, and is not optional.

**Use `gzip` and `zlib` on their own** to read or write a header without
decompressing anything.

## The rules a user needs

1. **`feed` hands back bytes it has not verified.** The checksum is in the
   trailer, so a streaming decoder cannot check as it goes. Only a successful
   `finish` says the output was correct. A caller who cannot tolerate that
   buffers until `finish` returns, or uses `decompress`, which does.
2. **A chunk may split anything**: a Huffman code, a length and distance pair,
   the two bytes of a zlib header, the gzip trailer between its checksum and its
   length. Whatever a chunk could not finish is carried in the decoder and
   completed by the next one.
3. **There is no default size limit, and DEFLATE can expand roughly a
   thousandfold.** A decoder with no bound will one day be handed a compression
   bomb. `inflate.with_limit` states the bound, and exceeding it is
   `OutputTooLarge(offset, cap)`. The right bound is how much memory you are
   willing to spend, which is why there is no default.
4. **`gzip.header()` defaults the modification time to 0 and the operating
   system byte to 255.** `gzip(1)` writes the real time and the real platform;
   this package reads no clock. Pass the real time to `gzip.with_mtime` if you
   want one.
5. **`gzip.with_name` does not sanitise the name, and nor does the parser.**
   RFC 1952 section 2.3.1 says the field is a base name with no directory, and a
   decompressor that honoured a path in it would have a directory-traversal
   hole. This package has no filesystem to check against. **A caller extracting
   to disk must sanitise what `inflate.gzip_header` returned before using it as
   a file name.**
6. **Trailing bytes after the end of a stream are accepted by default.** gzip
   files legitimately concatenate members and padded archives are everywhere.
   `inflate.with_strict` turns that into `TrailingGarbage(offset)`.
7. **A checksum mismatch does not retract the output already handed out.** The
   bytes the earlier `feed` calls produced are still the caller's: someone
   recovering a damaged archive wants the prefix.
8. **Every decoding error carries the byte offset in the compressed stream**
   where the decoder stopped, in a form a person can pass to `xxd -s`.
   `flateerror.offset_of` reads it out.

The refusals are `BadStoredLength(offset, len, nlen)`, `BadBlockType(offset)`,
`BadHuffmanCode(offset)`, `IncompleteHuffmanTable(offset, symbol)`,
`BadDistance(offset, distance, available)`, `TruncatedStream(offset)`,
`BadZlibHeader(offset, cmf, flg)`, `ZlibDictionaryRequired(offset, id)`,
`BadGzipMagic(offset, saw)`, `BadGzipMethod(offset, method)`,
`BadGzipHeaderCrc(offset, want, got)`, `ChecksumMismatch(offset, want, got)`,
`GzipLengthMismatch(offset, want, got)`, `TrailingGarbage(offset)`,
`OutputTooLarge(offset, cap)`, `BadLevel(level)` and `SourceFailed(cause)`.

Four of them are worth distinguishing from the rest.

- `TruncatedStream` means the input simply stopped. The fix is to find the rest
  of the file, not to repair anything.
- `ZlibDictionaryRequired` is "not supported", not "corrupt". The `id` is the
  Adler-32 of the dictionary the encoder used, which is the only handle a caller
  has for finding it.
- `GzipLengthMismatch` is separate from `ChecksumMismatch` because a matching
  checksum with a wrong length means a truncated member followed by something
  else, and a caller scanning a multi-member file needs to know which.
- `BadLevel` and `SourceFailed` carry no offset: the first is a fault in the
  call that built the encoder, and the second happened before the decoder
  reached a byte to blame.

## Running on a microcontroller

The state a decoder carries is a 32 KiB window, a bit buffer and a dozen
integers, because RFC 1951 section 4 caps a back-reference at 32768 bytes. That
is a hard ceiling rather than a heuristic, which is what lets this package fit on
a small device.

## What is not included

- **Preset dictionaries.** A zlib stream compressed against one is reported as
  `ZlibDictionaryRequired` with the dictionary's identifier, and decoding stops
  there.
- **A decompress-from-a-callback interface** of the kind zlib calls
  `inflateBack`.
- **File helpers.** This package opens nothing.
- **gzip's extra-field subfield registry.** A subfield belongs with the
  application that defined it.
- **A default size limit.** See rule 3.

## Related packages

This package has no dependencies. The bit reader, the Huffman decoder and both
checksums are hand-written passes over bytes the caller already holds.

[zip-nv](https://novo-lang.org/packages/zip-nv) is built on it: a ZIP entry is a
raw DEFLATE stream with the archive's own headers around it.

## The reference implementation

zlib is the reference implementation and its corpus is the oracle. The
distinction below decides what a test may assert.

**Specification, and binding on this package.**

- The DEFLATE bit stream: block types, the fixed and dynamic Huffman alphabets,
  the length and distance codes, the 32768-byte window cap, and the final-block
  flag (RFC 1951).
- The zlib container: compression method 8, the window bits, the dictionary
  flag, the requirement that the two header bytes read big-endian be a multiple
  of 31, and the big-endian Adler-32 trailer (RFC 1950).
- The gzip container: the `1f 8b` magic, compression method 8, the flag bits and
  the optional fields they gate, and the little-endian CRC32 and length trailer
  (RFC 1952).
- Adler-32's modulus and seed, and CRC32's reflected IEEE polynomial.

**zlib's own choices, which this package follows and a test may not treat as
correctness.**

- That compression levels exist at all, and that they run 0 to 9 with 6 as the
  default. RFC 1951 says nothing about a level; a conforming encoder may emit
  any valid stream at any of them.
- `FlateStrategy` entirely — filtered, Huffman-only, run-length and fixed. All
  four are zlib inventions, and every one produces a stream any decoder reads.
- Where blocks are split, when a table carried in the block beats the fixed one,
  and how far the match search looks. This is where an encoder's output size
  comes from, and none of it is specified.

The correctness condition is therefore: **zlib inflates what this deflates, and
this inflates what zlib deflates.** Byte-for-byte equality with zlib's output at
the default level is not a condition, and a test that asserted it would be
testing this encoder's block-splitting heuristics rather than DEFLATE.

## How the encoder compresses

The encoder holds input until it has a block, 65,535 bytes. It breaks the block
into literals and back-references with a hash-chain search over the block and
the 32 KiB before it, and at levels 4 to 9 it looks one position ahead for a
longer match before taking the one in hand. The search effort at each level is
zlib's. The block is then written as whichever of the three block types is
smallest: stored, fixed codes, or codes built for that block. Code lengths are
limited to 15 bits.

The ratio is close to zlib's on text and equal on data that does not compress
(the block is stored), and it is not identical: the same input does not give
the same bytes. A test that compares compressed bytes with zlib's tests the
block-splitting heuristics, which no specification fixes.

`FlateHuffmanOnly` skips the search, `FlateRle` searches only for a repeat of
the previous byte, `FlateFiltered` ignores matches shorter than six bytes, and
`FlateFixed` never builds a table.

A zlib header that promises a smaller window (`zlib.with_window_bits`) makes the
encoder keep its matches inside that window.

## Memory

A decoder holds the last 32 KiB of output and the few bytes of an unfinished
code. Each `feed` also builds its output in a buffer of its own, so the peak is
the window plus the output one chunk produces. The encoder holds up to one
block of input, the 32 KiB before it, and while it encodes a block, a hash head
table of up to 32,768 integers and one integer per input byte.

## Specifics worth knowing

- The three block types and both containers are read and written to the
  specification. A dynamic block header that declares more than 286 literal and
  length codes or more than 30 distance codes is `BadHuffmanCode`.
- A literal and length code, or a distance code, that is incomplete is
  `IncompleteHuffmanTable`, except the single one-bit distance code that RFC
  1951 section 3.2.7 allows. A block may also declare no distance codes at
  all.
- `is_corrupt` is false for `TruncatedStream` and `SourceFailed` and true for
  every other reason.
- The checksum and length of a stream are verified when the trailer arrives,
  inside `feed`; the failure is recorded in the decoder and `finish` reports
  it.
- After the end of a stream the decoder keeps nothing: bytes that follow are
  dropped, and `total_in` is the offset of the first of them.
- `zlib.emit` panics for a header whose window or level hint is out of range,
  as its documentation says; `zlib.emit_checked` is the form that answers an
  error.

## Licence

Apache-2.0. See `LICENSE`.
