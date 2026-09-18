#!/usr/bin/env python3
"""Cut the committed conformance subsets out of the UCD's own test files.

    python3 tools/gen_conformance.py <ucd-directory> [--tests tests]

`GraphemeBreakTest.txt`, `WordBreakTest.txt` and `NormalizationTest.txt`
are the oracle for UAX #29 and UAX #15.  They are the annexes' own
answers, written in the annexes' own notation, and an implementation
that agrees with them is conformant by definition rather than by
somebody's reading.

A subset is committed and the whole files are not.  The three come to
3.3 MB, the Consortium publishes them, and a copy here would be a
second original that goes stale the next release.  What is committed is
a deterministic sample.  It is the opening cases, which are the basic
rules, and then every Nth case, which spreads the rest over the whole
file, so `novo test` proves conformance on a fixed corpus with no
network and no download.

The same suites run the whole files, with `NOVO_UCD` naming a directory
holding them:

    NOVO_UCD=/path/to/ucd novo test tests/uax29_tests.nv
    NOVO_UCD=/path/to/ucd novo test tests/uax15_tests.nv

The reader is the same reader; only the corpus is bigger.  That is the
point of shipping the reader rather than a list of expected answers.
"""

import os
import sys

# How many of the opening cases to take whole, and how often to sample
# afterwards.  The opening cases of each file are the rules in their
# simplest form; the stride is what carries the rest of the file in.
HEAD = 24
STRIDE = 13

# NormalizationTest.txt is twenty times the size and its sections are
# grouped by script, so it gets its own, wider stride.
NORM_HEAD = 24
NORM_STRIDE = 61


def cases(path):
    """Every non-comment, non-empty line of a UCD test file."""
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            # `@Part1` and its siblings are section headers, not cases.
            if line and not line.startswith("@"):
                out.append(line)
    return out


def sample(rows, head, stride):
    """The opening `head` rows, then every `stride`th of the rest."""
    picked = rows[:head]
    picked += rows[head::stride]
    return picked


# The suite file keeps its hand-written reader and its `@test`
# functions; only the sample between these two lines is generated, the
# way the stdlib pages carry their generated tables.
BEGIN = "// BEGIN GENERATED CASES: %s"
END = "// END GENERATED CASES: %s"


def write_const(tests, name, const, rows, note, total):
    """Replace the generated region of a suite file with a new sample."""
    file_path = os.path.join(tests, name)
    with open(file_path, encoding="utf-8") as fh:
        text = fh.read()
    head = BEGIN % const
    tail = END % const
    a = text.index(head)
    b = text.index(tail)
    block = [head]
    block += ["// " + l if l else "//" for l in note.strip().split("\n")]
    block += [
        "//",
        "// The whole file holds %d cases and this is %d of them."
        % (total, len(rows)),
        "// They are the opening cases, which are the rules in their simplest",
        "// form, and then a fixed stride through the rest.  `NOVO_UCD` runs",
        "// the whole file through the same reader.",
        'const %s = "%s"' % (const, "\\n".join(rows)),
        "",
    ]
    with open(file_path, "w", encoding="utf-8") as fh:
        fh.write(text[:a] + "\n".join(block) + text[b:])
    print("%-24s %-22s %5d of %6d cases" % (name, const, len(rows), total))


def main():
    if len(sys.argv) < 2:
        sys.stderr.write(__doc__)
        return 2
    ucd = sys.argv[1]
    tests = "tests"
    if "--tests" in sys.argv:
        tests = sys.argv[sys.argv.index("--tests") + 1]

    g = cases(os.path.join(ucd, "auxiliary", "GraphemeBreakTest.txt"))
    write_const(
        tests, "uax29_tests.nv", "GRAPHEME_CASES",
        sample(g, HEAD, STRIDE),
        "A case is a run of codepoints with `\\u{00F7}` where a cluster\n"
        "boundary falls and `\\u{00D7}` where one does not, starting and\n"
        "ending with a boundary (GB1 and GB2).",
        len(g))

    w = cases(os.path.join(ucd, "auxiliary", "WordBreakTest.txt"))
    write_const(
        tests, "uax29_tests.nv", "WORD_CASES",
        sample(w, HEAD, STRIDE),
        "The same notation as the grapheme file, for the word boundaries of\n"
        "UAX #29 section 4.",
        len(w))

    n = cases(os.path.join(ucd, "NormalizationTest.txt"))
    write_const(
        tests, "uax15_tests.nv", "NORMALIZATION_CASES",
        sample(n, NORM_HEAD, NORM_STRIDE),
        "A case is five semicolon-separated columns of codepoints.  They\n"
        "are the source, its NFC, its NFD, its NFKC and its NFKD, and the\n"
        "annex's conformance clause is the twenty equalities they imply.",
        len(n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
