# unicode-nv

The Unicode Character Database is the set of files that record, for
every codepoint, what kind of character it is: its general category,
its case mappings, its decompositions, its East Asian width and the
properties text segmentation is defined over. It is published by the
Unicode Consortium and described in
[UAX #44](https://www.unicode.org/reports/tr44/). This package brings
that database to novo-lang as a library, together with the algorithms
defined over it. [textwrap-nv](https://novo-lang.org/packages/textwrap-nv),
[markdown-nv](https://novo-lang.org/packages/markdown-nv),
[slug-nv](https://novo-lang.org/packages/slug-nv),
[fuzzy-nv](https://novo-lang.org/packages/fuzzy-nv) and
[diff-nv](https://novo-lang.org/packages/diff-nv) are built on it.

The tables are generated from the Unicode 16.0.0 database.

## What it is

A **codepoint** is a number the Unicode standard assigns to a
character, written `U+0041` for the Latin capital A. A **grapheme
cluster** is what a reader calls one character: a base letter with its
combining marks, a flag written as two regional indicators, a family
emoji written as seven codepoints joined by zero-width joiners.
Counting a string in codepoints and counting it in grapheme clusters
give different numbers, and the second one is what a cursor, a
backspace and a truncation are about.
[UAX #29](https://www.unicode.org/reports/tr29/) defines where the
cluster boundaries fall, and also where the word boundaries fall.

**Display width** is how many cells of a terminal grid a character
occupies. The answer is 0, 1 or 2 and never anything else. A combining
mark takes none, a CJK ideograph or a fullwidth form takes two, and
everything else takes one.
[UAX #11](https://www.unicode.org/reports/tr11/) defines the East Asian
Width property that decides it, and every terminal adds the zero-width
categories to that.

**Normalisation** is turning text into a single canonical spelling.
The letter "é" is two different strings: one codepoint, or an "e"
followed by a combining acute accent. They look identical and `==` says
they differ. [UAX #15](https://www.unicode.org/reports/tr15/) defines
four forms. NFD decomposes, NFC decomposes and then recomposes, and
NFKD and NFKC do the same after also replacing compatibility
characters, so that the ligature "ﬁ" becomes "fi". The macOS filesystem
hands out NFD and almost everything else hands out NFC.

**Case mapping** turns text into upper, lower or title case. It is not
the ASCII operation. A mapping is not one to one, because "ß"
uppercases to "SS". It is therefore not length preserving. It depends
on the language, because Turkish "i" uppercases to a dotted capital.
**Case folding** is a fourth operation, and it is not lowercasing. A
fold is a comparison key that maps "ß" and "ss" to the same value, and
its output is not text to show a user.

**The general category** is the one-of-thirty classification Unicode
gives every codepoint: uppercase letter, decimal number, open
punctuation, unassigned and so on.
[UAX #31](https://www.unicode.org/reports/tr31/) derives the identifier
properties `ID_Start` and `ID_Continue` from it, and their
normalisation-closed variants `XID_Start` and `XID_Continue`. A lexer
written against "a letter or an underscore" disagrees with every other
language about the same source file.

## Install

```
novo pkg add unicode-nv
```

## Example

```novo
use uwidth
use ugrapheme
use uclass

fn main() [io]
    let text = "héllo 世界"

    // How many user-perceived characters the text holds, by UAX #29.
    println(str.from_int(ugrapheme.count(text)))

    // How many terminal cells it occupies, measured cluster by
    // cluster, so an ideograph counts as two and a combining mark
    // as none.
    println(str.from_int(uwidth.text_width(text)))

    // Whether U+0068 may start an identifier, by UAX #31.
    if uclass.is_xid_start(0x68)
        println("h may start an identifier")
```

Build and test with `novo pkg build` and `novo test`.

## What the package contains

| Module | Contents |
| --- | --- |
| `uwidth` | How many terminal cells a codepoint, a grapheme cluster or a whole string occupies, and the East Asian Width property it is derived from. |
| `ugrapheme` | Grapheme cluster and word boundaries by UAX #29, as a cursor over a string and as a state machine over one codepoint at a time. |
| `unorm` | The four normalisation forms, the quick check that answers without allocating, and canonical equivalence of two strings. |
| `ucase` | Upper, lower and title case under the full rules with the language as a parameter, and case folding for comparison. |
| `uclass` | The thirty general categories, the UAX #31 identifier predicates, and the character-class predicates a lexer asks for. |
| `udata` | The handle that carries the large tables, and the three ways of getting one. |

The package also ships four generated modules — `udbcore`, `udbcat`,
`udbcase` and `udbnorm` — and `utbl`, which searches them. Nothing in
them is public and a program never names them.

## How to choose an entry point

**`uwidth.char_width` is the width function other packages already
accept.** It takes one `Int` and returns one `Int`. textwrap-nv's
`WrapWidth` holds a value of exactly that type, so a caller writes
`WrapWidth { of_char: uwidth.char_width }` and changes nothing else.
`char_width_cjk` is the same function with ambiguous-width characters
counted as two cells, for a terminal the user has configured East
Asian.

**`uwidth.text_width` measures cluster by cluster; `str_width` sums
over codepoints.** Use `text_width` for text that may contain emoji.
Use `str_width` when you know it does not, because it never has to
segment.

**`ugrapheme.cursor` is for a caller holding the whole string.**
`cursor_next` answers the cluster at the cursor and `cursor_advance`
moves past it. `count`, `nth`, `clusters` and `next_boundary` are the
same walk packaged for common questions.

**`ugrapheme.break_step` is for a caller receiving one codepoint at a
time.** It takes a `UniBreakState` and a codepoint and answers whether
a boundary falls before that codepoint, together with the next state. A
terminal emulator driven by an escape-sequence parser never holds the
string, so this is the surface it uses. Both surfaces run the same
algorithm.

**`unorm.quick_check` and `unorm.compare` are the cheap answers.**
`quick_check` reports yes, no or maybe, allocating nothing, from one
table lookup per codepoint and at most one composition lookup.
`compare` decides canonical equivalence without building either
normalised form: when both strings are already in the form it compares
them as they stand and allocates nothing, and otherwise it normalises
one starter-run of each side at a time and stops at the first
difference. Call `normalize` when the normalised string is what you need
to keep.

**`ucase.fold` is for comparison and `ucase.to_lower` is for display.**
A caseless match uses `fold` or `eq_fold`. A program that lowercases in
order to compare has a bug on German input.

## The rules a user needs

1. **A grapheme cluster is not a codepoint, and neither is a byte.**
   UAX #29 section 3.1 defines extended grapheme clusters, including
   rule GB9c for Indic conjuncts and rule GB11 for emoji sequences
   joined by a zero-width joiner. Cursor movement, backspace,
   truncation and a character count are all questions about clusters.
2. **`char_width` answers 0, 1 or 2 and nothing else.** UAX #11
   section 5 gives the East Asian Width property. A codepoint that is
   not a character, such as an unpaired surrogate, answers 1, because a
   terminal draws it as a replacement glyph and a replacement glyph
   occupies a cell.
3. **Ambiguous-width characters cannot be resolved by this package.**
   UAX #11 section 5 class A covers the Greek and Cyrillic letters
   among others. A terminal in a CJK locale draws them two cells wide
   and every other terminal draws them one. `char_width` answers 1 and
   `char_width_cjk` answers 2. Only the program knows which terminal it
   is talking to.
4. **Summing `char_width` over a string is wrong wherever emoji
   appear.** A flag is two regional indicators and a family is up to
   seven codepoints. Per codepoint the sum comes out four cells or one.
   `cluster_width` and `text_width` are the functions that get those
   right.
5. **Compare text only after normalising it.** UAX #15 section 1.1 is
   the case for it. Every filename comparison, login, cache key and
   deduplication over text a user typed is wrong until one side has
   normalised.
6. **NFKD and NFKC are lossy on purpose.** UAX #15 section 1.2: a
   compatibility decomposition replaces the superscript "²" with "2"
   and the ligature "ﬁ" with "fi". Use them for an identifier
   comparison or a search index. Do not store the result in place of
   the original.
7. **Case mapping may change the length of a string.** The Unicode
   Standard section 5.18 and the database file `SpecialCasing.txt`
   give the multi-character mappings. An index kept across a case
   conversion, or a fixed-size buffer sized from the input, breaks on
   real names.
8. **Pass the language to `to_lower`, `to_upper` and `to_title`.**
   `LANG_ROOT` is the default rules. `LANG_TURKISH` and `LANG_AZERI`
   give Turkish the four letters it has rather than two.
   `LANG_LITHUANIAN` keeps the dot above an accented lowercase "i". A
   Turkish system that uppercases "i" to "I" produces a different word.
9. **`ucase.fold` takes no language.** A fold is a comparison key, and
   a key that depended on the reader's locale would make two systems
   disagree about whether two strings match. `simple_fold` reaches the
   Turkic variant for a caller that needs it.
10. **`unorm`, `ucase` and `uclass.category` take a `UniData`; nothing
    else does.** The parameter is the disclosure that the call reaches
    a large table. See the table under "Running on a microcontroller".
11. **Ask `udata.data_covers` before trusting an answer from a partial
    handle.** `data_full()` covers every codepoint. `data_compact()`
    covers the Basic Multilingual Plane only, and its `complete` field
    is false. A codepoint a handle does not cover is treated as having
    no mapping and no decomposition, which is the identity answer and
    is indistinguishable from a character that genuinely has none.
    `data_compact()` does not make the program smaller: it reads the
    same compiled-in tables and refuses above U+FFFF. A packed table
    holding only what a program needs is what makes it smaller.
12. **`udata.data_from_pack` borrows the bytes it is given.** Every
    later lookup reads out of that slice, so the caller keeps it alive
    for as long as the `UniData`. It answers `None` when the blob does
    not begin with `PACK_MAGIC`, when its declared length disagrees
    with what was handed over, or when its format version is unknown.
13. **A `UniCluster` is a byte range, not a string.** `start` is
    inclusive and `end` is exclusive, both in bytes into the string the
    cluster came from. Segmenting and then slicing is the intended use.
14. **The ASCII predicates answer a narrower question.**
    `uclass.is_ascii_digit` and its neighbours are not a fast path for
    the Unicode ones. On non-ASCII input they answer `false`, which is
    correct for a lexer whose identifiers are ASCII and wrong for
    anything else.
15. **A tokenizer wants `is_xid_start` and `is_xid_continue`.**
    UAX #31 section 2 defines them as the normalisation-closed forms of
    `ID_Start` and `ID_Continue`. They are the right predicates when
    identifiers are compared after NFKC.
16. **`unorm.compare` orders by the normalised form, not by the input.**
    "A" with a combining ring composes to "Å", which sorts after "B".
    Two strings that are canonically equivalent compare equal whichever
    spelling arrived, which is the property a sort key needs; the order
    of two that are not equivalent is the order of the forms.
17. **`unorm.quick_check` may answer `QcNo` where UAX #15's table alone
    answers maybe.** The table says maybe for a mark that might compose
    with what precedes it; this checks whether it actually does, with
    one more lookup and no allocation. `QcYes` and `QcNo` are both
    certain, and `QcMaybe` still means the full algorithm has to run.

## Running on a microcontroller

`uwidth`, `ugrapheme` and `uclass`'s predicates build for a device with
no heap allocator, and the rest of the package does not. They read
tables of about 38 KB in total, which is what a device driving a serial
console or a small display needs. The compiler checks that on every
build, on a host as well as for a board.

`tests/embedded_probe.nv` is those modules as a device program. It
builds a Cortex-M4 executable that runs eight checks over the width
rule, the break state machine and the ASCII and scalar predicates.

```bash
novo build --target=nrf52-qemu tests/embedded_probe.nv
```

That command was run against this release and produced an executable of
77 KB, with the width, break and predicate tables in it and none of the
other three.

The tables read correctly on a device under a toolchain newer than
0.9.1, where the length of a text constant on the embedded runtime
counts the whole constant. Under 0.9.1 that length stops at the first
zero byte, and because every table here opens with the entry for
U+0000 the three checks that read a table answer wrongly. The same
tables are correct on a host under either toolchain.

`unorm` and `ucase` do not build for a device. Their tables are about
129 KB generated, which is half of an nRF52's flash. Firmware that
genuinely needs normalisation reads a packed table out of an external
flash region and passes the bytes to `udata.data_from_pack`.

| Table | Size | Entries | Where it lives |
| --- | --- | --- | --- |
| Display width | 5,320 bytes | 1,330 | Compiled in, no argument |
| Grapheme and word breaks | 15,395 bytes | 3,079 | Compiled in, no argument |
| Identifier and class predicates | 17,990 bytes | 3,598 | Compiled in, no argument |
| General category, all thirty | 16,396 bytes | 4,099 | Behind `UniData` |
| Case mapping, special casing, folding | 56,351 bytes | 5,833 | Behind `UniData` |
| Normalisation | 75,642 bytes | 14,888 | Behind `UniData` |

The three compiled-in tables are 38,705 bytes and the three behind
`UniData` are 148,389 bytes, for 187,094 bytes in total. The sizes are
generated from the Unicode 16.0.0 database by `tools/gen_tables.py`. A
program that never names `udata.data_full` gives the linker no reason to
keep the last three tables.

A table is a text constant holding one byte per byte of data, searched
by halving. An entry is a three-byte codepoint and one, two or three
bytes of value. A table records the places a property changes rather
than one entry per codepoint, which is why a property defined over 1.1
million codepoints fits in a few kilobytes.

## What is not included

- **Line breaking, UAX #14.** A larger algorithm with a larger table
  and a different consumer. Treating it as a small addition to a
  grapheme segmenter is how a package ends up with a wrong one.
- **Bidirectional text, UAX #9.** The same, at greater length.
- **Collation, UTS #10.** A sort order belongs to a locale rather than
  to a character. `unorm.compare` orders by normalised form, which is a
  different and much weaker promise, and says so.
- **Script and block properties.** No consumer on the registry needs
  them yet. They are a minor version bump when one does.
- **Legacy grapheme clusters.** The definition from before Unicode 9,
  which splits a base character from its combining marks. Nothing
  should be written against it.
- **A locale database.** Plural rules, date formats and message
  catalogues are [i18n-nv](https://novo-lang.org/packages/i18n-nv).
- **Reading the database text files at run time.** A `core` package
  performs no input, the files are 2 MB of ASCII, and parsing them at
  start-up is a cost every program pays for a table that never changes.
  `udata.data_from_pack` takes the packed form instead.
- **A build flag that selects a smaller table.** A package whose
  answers change with a build flag has tests that prove nothing about
  the build a user makes.

## Related packages

- [textwrap-nv](https://novo-lang.org/packages/textwrap-nv) wraps and
  fills paragraphs. It takes a width function as a parameter, and
  `uwidth.char_width` is the value it expects. Its own
  `monospace_width` answers 1 to every character, so a CJK line comes
  out too long until this package is passed in.
- [markdown-nv](https://novo-lang.org/packages/markdown-nv) needs
  `uclass.is_whitespace`, `is_punctuation` and `is_symbol` for
  CommonMark's emphasis rules.
- [slug-nv](https://novo-lang.org/packages/slug-nv) needs normalisation
  and case folding to turn a title into a URL path segment.
- [fuzzy-nv](https://novo-lang.org/packages/fuzzy-nv) and
  [diff-nv](https://novo-lang.org/packages/diff-nv) take the grapheme
  and word boundaries, so that a match highlight and a character-level
  diff both fall where a reader would put them.
- `std.str` in the standard library has ASCII case conversion and byte
  and codepoint indexing. It is the right tool for ASCII protocol text.
  It is the wrong tool for text a user typed.

## Tests

The reference implementations are **unicode-segmentation** and
**unicode-normalization** for the shape of the segmentation and
normalisation surfaces, **unicode-width** for the width rules,
**ICU4X** for the idea of passing the data tables as a value,
**Python's `unicodedata`** for the category vocabulary, and
**`wcwidth`** for what terminals are written against.

The expected answers come from the annexes' own test files, which this
release runs whole.

| File | Reference | Cases | Result |
| --- | --- | --- | --- |
| `GraphemeBreakTest.txt` | UAX #29 | 1,093 | all pass |
| `WordBreakTest.txt` | UAX #29 | 1,826 | all pass |
| `NormalizationTest.txt` | UAX #15 | 19,965 | all pass |

`NormalizationTest.txt` gives five columns per case — a source and its
NFC, NFD, NFKC and NFKD — and the conformance clause of UAX #15 is the
twenty equalities they imply. All twenty are checked on every case,
which is 399,300 assertions.

```bash
novo test tests/uwidth_tests.nv      # 11 tests: display width
novo test tests/ugrapheme_tests.nv   # 18 tests: UAX #29 boundaries
novo test tests/unorm_tests.nv       # 15 tests: the four forms
novo test tests/ucase_tests.nv       # 14 tests: mapping and folding
novo test tests/uclass_tests.nv      # 11 tests: categories and UAX #31
novo test tests/udata_tests.nv       #  6 tests: the three data handles
novo test tests/uax29_tests.nv       #  3 tests: the segmentation annex
novo test tests/uax15_tests.nv       #  3 tests: the normalisation annex
```

The last two run a committed sample of each annex file — the opening
cases and then a fixed stride through the rest — so the suite is green
on a machine that has never downloaded the database. Set `NOVO_UCD` to a
directory holding the three files and the same suites read them whole:

```bash
NOVO_UCD=/path/to/ucd novo test tests/uax29_tests.nv
NOVO_UCD=/path/to/ucd novo test tests/uax15_tests.nv
```

Measured line coverage over `src/` is 100%: 1,065 instrumented
statements, 1,065 executed, no exclusion marked anywhere.

`tools/alloc_scan.sh` compiles `tests/alloc_probe.nv` and reads the
emitted code for calls to the allocator. It reports 57 functions on the
width, break and predicate path and no allocation in any of them.

## Reproducing the tables

`tools/gen_tables.py` writes the four generated modules under `src/`
from the database files, and `tools/gen_conformance.py` writes the
committed samples into the two annex suites. Neither downloads
anything; both take a directory.

```bash
curl -O https://www.unicode.org/Public/16.0.0/ucd/UnicodeData.txt      # and the rest
python3 tools/gen_tables.py /path/to/ucd
python3 tools/gen_conformance.py /path/to/ucd
```

The files each script reads are named at the top of it. The database
files themselves are not in this repository: they are 8 MB of text the
Unicode Consortium publishes, and a copy here would be a second
original.

## Licence

Apache-2.0. See `LICENSE`.

<!-- docs/writing-a-readme.md is the style guide for this page. -->
