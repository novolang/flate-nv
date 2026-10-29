"""Writes the corpus section of tests/vectors_tests.nv to standard output.

The streams are what CPython's zlib and gzip modules produce for a few
fixed inputs at levels 0, 1, 6 and 9.  The Novo suite carries the result
as hex literals, so running the suite needs no Python; this script is
only the record of where the bytes came from.

    python3 -I tests/vectors.py > corpus.txt
"""
import gzip
import zlib

TEXT = (
    "Sphinx of black quartz, judge my vow. The quick brown fox jumps over "
    "the lazy dog. Pack my box with five dozen liquor jugs. How vexingly "
    "quick daft zebras jump! A quick brown fox jumps over the lazy dog, and "
    "the lazy dog sleeps; the fox is quick, the dog is lazy. Waltz, bad "
    "nymph, for quick jigs vex. Sphinx of black quartz, judge my vow."
).encode()


def noise(n, seed=12345):
    out = bytearray()
    x = seed
    for _ in range(n):
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        out.append((x >> 16) & 0xFF)
    return bytes(out)


INPUTS = [
    ("empty", b""),
    ("one", b"a"),
    ("hello", b"hello, hello, hello, hello"),
    ("text", TEXT),
    ("runs", b"a" * 1000),
    ("noise", noise(200)),
    ("mixed", TEXT + noise(60) + TEXT[:100] + b"\x00" * 300),
]


def raw(data, level):
    c = zlib.compressobj(level, zlib.DEFLATED, -15)
    return c.compress(data) + c.flush()


def wrapped(data, level):
    return zlib.compress(data, level)


def member(data, level):
    return gzip.compress(data, level, mtime=0)


def main():
    print("// plain inputs, as hex")
    print("fn plain(name: Str) -> Bytes")
    for name, data in INPUTS:
        print('    if name == "%s"' % name)
        print('        return hex("%s")' % data.hex())
    print("    bytes.zeros(0)")
    print()
    print("// streams: (name, input, container, level, hex)")
    print("fn corpus() -> [Stream]")
    print("    var out: [Stream] = []")
    for name, data in INPUTS:
        for level in (0, 1, 6, 9):
            print('    list.push(out, Stream { input: "%s", format: 0, level: %d, hex: "%s" })'
                  % (name, level, raw(data, level).hex()))
    for name, data in INPUTS:
        if name in ("empty", "text", "runs", "noise", "mixed"):
            for level in (1, 6, 9):
                print('    list.push(out, Stream { input: "%s", format: 1, level: %d, hex: "%s" })'
                      % (name, level, wrapped(data, level).hex()))
                print('    list.push(out, Stream { input: "%s", format: 2, level: %d, hex: "%s" })'
                      % (name, level, member(data, level).hex()))
    print("    out")


main()
