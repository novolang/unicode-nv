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

**Status: NOT IMPLEMENTED — interface only.** Every function is declared
with its full signature, but every body is a `todo()` that panics when
called. The package is published so its design can be reviewed and
depended on before it is implemented. Version 0.1.0 will be the first
working release.

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

Build and test with `novo pkg build` and `novo test`. Today `novo test`
fails on purpose: every test reaches a
`not implemented: unicode-nv.<module>.<fn>` panic. The tests are the
specification the implementation will have to satisfy.

## What the package contains

| Module | Contents |
| --- | --- |
| `uwidth` | How many terminal cells a codepoint, a grapheme cluster or a whole string occupies, and the East Asian Width property it is derived from. |
| `ugrapheme` | Grapheme cluster and word boundaries by UAX #29, as a cursor over a string and as a state machine over one codepoint at a time. |
| `unorm` | The four normalisation forms, the quick check that answers without allocating, and canonical equivalence of two strings. |
| `ucase` | Upper, lower and title case under the full rules with the language as a parameter, and case folding for comparison. |
| `uclass` | The thirty general categories, the UAX #31 identifier predicates, and the character-class predicates a lexer asks for. |
| `udata` | The handle that carries the large tables, and the three ways of getting one. |

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

**`unorm.quick_check` and `unorm.compare` answer without allocating.**
`quick_check` reports yes, no or maybe from one table lookup per
codepoint. `compare` decides canonical equivalence without building
either normalised form. Call `normalize` when the normalised string is
what you need to keep.

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

## Running on a microcontroller

novo-lang lets a package state which of its modules can run on a device
with no heap allocator, and the compiler checks that claim on every
build. Here the claim covers `uwidth`, `ugrapheme` and `uclass`'s
predicates. Those read tables of about 27 KB in total, which is what a
device driving a serial console or a small display needs.

`tests/embedded_probe.nv` is that claim as a program. It builds a
Cortex-M4 executable that runs eight checks over the width rule, the
break state machine and the ASCII and scalar predicates.

```bash
novo build --target=nrf52-qemu tests/embedded_probe.nv
```

That command was run against this release and produced an executable.

**What the probe proves today is narrower than what it will prove.**
Every body under `src/` is a `todo()`, so what links is the signatures
and the types. No table is in the binary yet, so the probe does not yet
show that 27 KB fits. It shows that nothing in the shape of the surface
needs an allocator or a host.

`unorm` and `ucase` are outside the claim. Their tables are about
245 KB generated, which is most of an nRF52's flash. Firmware that
genuinely needs normalisation reads a packed table out of an external
flash region and passes the bytes to `udata.data_from_pack`.

| Table | Size | Where it lives |
| --- | --- | --- |
| Display width | 4 KB | Compiled in, no argument |
| Grapheme and word breaks | 11 KB | Compiled in, no argument |
| Identifier and class predicates | 12 KB | Compiled in, no argument |
| General category, all thirty | 40 KB | Behind `UniData` |
| Case mapping, special casing, folding | 55 KB | Behind `UniData` |
| Normalisation | 190 KB | Behind `UniData` |

The sizes are generated from the Unicode 16.0 database. A program that
never names `udata.data_full` gives the linker no reason to keep the
last three rows.

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

The expected answers come from the annexes' own test files, which the
implementation will run whole.

| File | Reference | Cases |
| --- | --- | --- |
| `GraphemeBreakTest.txt` | UAX #29 | about 1100 |
| `WordBreakTest.txt` | UAX #29 | about 1800 |
| `NormalizationTest.txt` | UAX #15 | about 19 000 |
| `SpecialCasing.txt`, `CaseFolding.txt` | UAX #44 | the case mappings |
| `EastAsianWidth.txt` | UAX #11 | the width classes |

```bash
novo test --isolate tests/uwidth_tests.nv      #  8 tests: display width
novo test --isolate tests/ugrapheme_tests.nv   # 12 tests: UAX #29 boundaries
novo test --isolate tests/unorm_tests.nv       # 11 tests: the four forms
novo test --isolate tests/ucase_tests.nv       #  9 tests: mapping and folding
novo test --isolate tests/uclass_tests.nv      #  9 tests: categories and UAX #31
```

The suites carry the cases from those files that explain why a rule
exists, each citing the line it came from in the annex's own notation.
The generated whole-file suites land with the bodies. The first test in
`uwidth_tests.nv` asserts that `char_width` is still the one-argument
function textwrap-nv holds.

The tests compile today and fail at run, each on the
`not implemented: unicode-nv.<module>.<fn>` panic that is its body.
That is the expected state of an interface release. They turn green one
at a time as bodies land.

## Implementation status

| Item | Implemented |
| --- | --- |
| `udata.UNICODE_VERSION`, `.PACK_MAGIC` | yes (they are constants) |
| `ucase.LANG_ROOT`, `.LANG_TURKISH`, `.LANG_AZERI`, `.LANG_LITHUANIAN` | yes (they are constants) |
| `ugrapheme.BREAK_START` | yes (it is a constant) |
| `uwidth.char_width`, `.char_width_cjk`, `.str_width`, `.cluster_width`, `.text_width`, `.fit_prefix` | no |
| `uwidth.east_asian_width`, `.is_wide`, `.is_zero_width`, `.is_ambiguous` | no |
| `ugrapheme.break_state`, `.break_step` | no |
| `ugrapheme.cursor`, `.cursor_at`, `.cursor_next`, `.cursor_advance`, `.cursor_done` | no |
| `ugrapheme.next_boundary`, `.prev_boundary`, `.is_boundary`, `.count`, `.nth`, `.clusters`, `.truncate_clusters` | no |
| `ugrapheme.next_word`, `.prev_word`, `.words` | no |
| `unorm.normalize`, `.normalize_into`, `.quick_check`, `.is_normalized` | no |
| `unorm.compare`, `.equivalent`, `.stream_boundary` | no |
| `unorm.combining_class`, `.decompose_char`, `.compose_pair`, `.is_starter` | no |
| `ucase.to_lower`, `.to_upper`, `.to_title`, `.fold`, `.eq_fold` | no |
| `ucase.to_lower_into`, `.to_upper_into`, `.fold_into` | no |
| `ucase.simple_lower`, `.simple_upper`, `.simple_title`, `.simple_fold`, `.full_lower`, `.full_upper` | no |
| `ucase.is_cased`, `.changes_when_folded` | no |
| `uclass.category`, `.category_abbrev`, `.category_named` | no |
| `uclass.is_letter`, `.is_digit`, `.is_alphanumeric`, `.is_whitespace`, `.is_control`, `.is_mark`, `.is_punctuation`, `.is_symbol`, `.is_uppercase`, `.is_lowercase` | no |
| `uclass.is_id_start`, `.is_id_continue`, `.is_xid_start`, `.is_xid_continue` | no |
| `uclass.is_ascii`, `.is_ascii_digit`, `.is_ascii_alpha`, `.is_ascii_whitespace`, `.is_valid_scalar` | no |
| `udata.data_full`, `.data_compact`, `.data_from_pack`, `.pack_bytes`, `.data_version`, `.data_covers` | no |

## Licence

Apache-2.0. See `LICENSE`.

<!-- docs/writing-a-readme.md is the style guide for this page. -->
