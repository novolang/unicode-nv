# unicode-nv

**Status: NOT IMPLEMENTED — interface only.**

Every public function below is published with its signature and its
effect row, and every body is `todo()`. Installing this package works;
calling it panics with `not implemented`.

## What this is

The Unicode character database, as a library a `core` package can use.

- `uwidth` — how many terminal cells a codepoint takes;
- `ugrapheme` — where one user-perceived character ends, by UAX #29;
- `unorm` — the four normalisation forms;
- `ucase` — case mapping and folding under the full rules;
- `uclass` — the categories and the identifier predicates;
- `udata` — the tables, and where they live.

```
novo pkg add unicode-nv
novo pkg build
novo test
```

## The one example that will work

```novo ignore
use uwidth
use ugrapheme

// The whole of what a terminal needs from this package, and the whole
// of why it is `core`: a width, and a boundary, and no machine.
fn columns_used(text: Str) -> Int
    var total = 0
    var c = ugrapheme.cursor(text)
    while ugrapheme.cursor_done(c) == false
        match ugrapheme.cursor_next(c)
            None      =>
                c = ugrapheme.cursor_advance(c)
            Some(cl)  =>
                total = total + uwidth.cluster_width(str.slice(text, cl.start, cl.end))
                c = ugrapheme.cursor_advance(c)
    total
```

## The load-bearing interface

Two functions, and the first one's shape was decided by a package that
is already published.

```novo ignore
// uwidth — the exact `fn(Int) -> Int` textwrap-nv's WrapWidth holds.
pub fn char_width(ch: Int) -> Int []

// ugrapheme — the break algorithm as a state machine over one
// codepoint at a time.
pub fn break_step(s: UniBreakState, ch: Int) -> UniBreakStep []

pub struct UniBreakStep
    state: UniBreakState
    boundary: Bool          // a boundary falls BEFORE this codepoint
```

**`char_width` is one argument because textwrap-nv says so.**
textwrap-nv is published, and it takes the width of a codepoint as a
parameter *because this package did not exist*:

```novo ignore
pub struct WrapWidth
    of_char: fn(Int) -> Int
```

So landing unicode-nv has to be one line at a consumer's call site —
`WrapWidth { of_char: uwidth.char_width }` — and no change to any
signature textwrap-nv published. That rules out a width function that
takes a table, which rules out a caller-supplied width table, which is
what decides the whole table layout below. The consumer's signature is
the constraint; everything else follows from it.

**`break_step` exists because the consumer that asked for this package
never holds the string.** A terminal emulator gets text from a VTE
parser one codepoint at a time — novo-vte hands out
`AnsiPrint(ch: Int)` — and has to decide, for each one, whether it
opens a new cell or joins the last. A segmenter that needs the whole
string is no use to it. The string functions (`count`, `nth`,
`next_boundary`, `clusters`) are written on top of the same machine, so
the two surfaces cannot disagree.

## The table layout, which is the package's one real decision

`core` may not read a file, so every table is either a constant in the
binary or bytes the caller handed over. The sizes, generated from
Unicode 16.0's UCD:

| what | size | where it lives |
| --- | --- | --- |
| display width (EAW + Mn/Me/Cf + emoji presentation) | ~4 KB | compiled in, no argument |
| grapheme and word breaks (UAX #29 + Extended_Pictographic) | ~11 KB | compiled in, no argument |
| identifier and class predicates (XID, White_Space, …) | ~12 KB | compiled in, no argument |
| general category, all thirty | ~40 KB | behind `UniData` |
| case mapping, special casing, folding | ~55 KB | behind `UniData` |
| normalisation: decompositions, exclusions, combining classes | ~190 KB | behind `UniData` |

**Tier one — always there, no argument.** 27 KB, and a device with
256 KB of flash can hold it. `uwidth`, `ugrapheme` and `uclass`'s
predicates take no `UniData`, which is what lets `char_width` be the
`fn(Int) -> Int` above.

**Tier two — compiled in, but asked for by name.** `unorm` and `ucase`
take a `UniData`, and `udata.data_full()` is the constructor that hands
them the generated tables. A program that never normalises never names
`data_full`, so the linker has no reason to keep 245 KB it cannot
reach. The parameter is the disclosure: a reader of a signature sees
that normalising costs a table, where a free function would have hidden
it.

**Tier three — parsed from bytes the host read.**
`udata.data_from_pack(blob: [u8])` takes the same tables as a byte
slice the caller got from a file, a flash region or an HTTP response.
The parse is arithmetic, so `core` stays sans-IO, and the firmware that
genuinely needs normalisation keeps 190 KB out of its text section.
This is the answer to *the embedded tier cannot carry all of them*: it
does not have to carry them, it has to be able to reach them.
`udata.data_compact()` is the middle option — the Basic Multilingual
Plane only, about a third of the size, with `complete = false` so a
caller can tell.

**What was rejected, and why**, because these are the options a reader
will ask about:

- *A caller-supplied table for everything.* It makes the width function
  take two arguments, which stops it being the value textwrap-nv
  already accepts, and pushes a table nobody wants to think about into
  every call site in a terminal.
- *A build flag — `@tier(embedded)` selecting a smaller table.* A
  package whose **answers** change with a build flag is a package whose
  tests prove nothing about the build a user makes. A string that
  normalises differently on two targets is worse than one that does not
  normalise at all.
- *Reading the UCD text files at run time.* `core` may not read, the
  files are 2 MB of ASCII, and parsing `UnicodeData.txt` at start-up is
  a cost every program pays for a table that never changes.
  `data_from_pack` takes the packed form for exactly that reason.

## The layer, and the device claim

`core` — no effects. Every answer is a lookup over a codepoint the
caller already holds.

`tests/embedded_probe.nv` makes the claim, and it covers **`uwidth`,
`ugrapheme` and `uclass` only**. `unorm` and `ucase` are deliberately
outside it: 245 KB is most of an nRF52's flash, and a claim that
included them would be one nobody could keep.

At 0.0.1 the probe proves less than it will. Every body is a `todo()`,
so what links today is the signatures and the types — no table is in
the binary yet, and the probe does not yet prove that 27 KB fits. It
proves that nothing in the shape of the surface needs an allocator or a
host. Keeping it green with the tables in is a named cost of the
implementation step, not a surprise waiting in it.

## Who is waiting for this

| consumer | what it takes | state today |
| --- | --- | --- |
| textwrap-nv | `uwidth.char_width` as its `WrapWidth.of_char` | `monospace_width()` answers 1 to everything, so a CJK line comes out too long |
| tui-nv | the same, through textwrap-nv's paragraph widget | inherits textwrap-nv's placeholder |
| orbit/novoterm, orbit/novomux | width per cell, and cluster boundaries per cell | their own per-codepoint arithmetic |
| markdown-nv | `uclass.is_whitespace`, `is_punctuation`, `is_symbol`, `ucase.fold` | the CommonMark emphasis rules cannot be spec-correct without them |
| table-nv, slug-nv, i18n-nv (planned) | widths, normalisation, plural rules | not written |

## Where the names come from, and the ones that were taken

Public type names are unique across the whole assembly, dependencies
included, so a package's names have to be unique across the registry
too.

| here | the obvious name | why not |
| --- | --- | --- |
| `UniCluster` | `Cluster`, or `Span` | generic enough that two packages will both want it; `Span` is a module name already in use |
| `UniCursor` | `Cursor` | `Cursor` is a **standard-library struct** (`std.cursor`) and pager-nv publishes one too |
| `UniBreakState`, `UniBreakStep` | `State`, `Step` | sql-engine-nv publishes `State`; `Step` is the single most-wanted name on the registry |
| `UniCategory` | `Category` | certain to collide, and `Cat…` on the variants keeps the thirty readable |
| `UniForm` | `Form` | generic; and `Form` will be wanted by form-nv, which is a planned row |
| `UniData` | `Data`, `Tables` | both generic; `UniData` also reads as *the Unicode data*, which is what it is |
| `UniWord`, `UniWordKind` | `Word`, `WordKind` | `Word` is what a tokenizer package will want |
| `UniEastAsian` | `EastAsianWidth` | not taken, but the `Uni` prefix is the package's convention and an exception would read as an oversight |
| module `uwidth` | `width`, `widths` | textwrap-nv already ships `widths.nv`, and two dependencies may not both ship a module of the same name — this is the collision that actually bites, because tui-nv takes both packages |
| module `unorm`, `ucase`, `uclass` | `normalize`, `case`, `class` | all three are names another package will want, and `case` is a keyword-shaped word |
| module `udata` | `data`, `tables` | same |

The module row is the one worth reading twice: `widths.nv` in
textwrap-nv and a `widths.nv` here would be a *build* failure for
tui-nv, which depends on both. The type rule and the module rule are
the same rule.

## The reference implementation

**unicode-segmentation** and **unicode-normalization** (Rust) for the
shape of the segmentation and normalisation surfaces, and their test
suites, which are the UCD's own files. **unicode-width** for the width
rules, including the two categories UAX #11 does not cover. **ICU4X**
for the tiered-data idea — its `DataProvider` is the same argument as
`UniData`, made for a bigger surface. **Python's `unicodedata`** for
the category and predicate vocabulary. **`wcwidth`** for what every
terminal is actually written against.

The oracles are the annexes' own test files, and they are what the
implementation lane runs whole:

- `GraphemeBreakTest.txt` and `WordBreakTest.txt` — UAX #29, about
  1100 and 1800 cases;
- `NormalizationTest.txt` — UAX #15, about 19,000 cases;
- `SpecialCasing.txt` and `CaseFolding.txt` — the case mappings;
- `EastAsianWidth.txt` — UAX #11.

The suites in `tests/` carry the cases from those files that explain
**why** a rule exists; the generated whole-file suites land with the
bodies.

Deliberately left out, and where it goes instead:

- **Line breaking (UAX #14).** A bigger algorithm with a bigger table
  and a different consumer. Pretending it is a small addition to a
  grapheme segmenter is how a package ends up with a wrong one.
- **Bidirectional text (UAX #9).** The same, more so.
- **Collation (UTS #10).** A sort order is a locale's, not a
  character's; `unorm.compare` orders by normalised form and says so,
  which is a different and much weaker promise.
- **Script and block properties.** Wanted, not needed by any consumer
  on the grid yet; a minor bump when one appears.
- **Legacy grapheme clusters.** The pre-Unicode-9 definition, which
  splits a base from its marks. Nothing should be written against it.
- **A locale database.** i18n-nv's row.

## Status

Every function is `todo()`. Five suites, all red, all for the same
reason — every assertion reaches `not implemented: unicode-nv.<fn>`,
which is the expected result until the bodies land.

```
novo test --isolate tests/uwidth_tests.nv      # display width, and the textwrap-nv contract
novo test --isolate tests/ugrapheme_tests.nv   # UAX #29, in the annex's own notation
novo test --isolate tests/unorm_tests.nv       # UAX #15, from NormalizationTest.txt
novo test --isolate tests/ucase_tests.nv       # SpecialCasing.txt and CaseFolding.txt
novo test --isolate tests/uclass_tests.nv      # the categories and UAX #31
```

`novo doc` renders and its examples compile.
