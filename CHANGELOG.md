# Changelog

All notable changes to unicode-nv are recorded here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
package follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
with the pre-1.0 rule that a breaking change bumps the MINOR number.

## 0.0.1 — 2026-09-11

The **interface**: every signature and every effect row, and no bodies.
`stability = "draft"`, and the release is recorded `implemented = false`.

### Added

- `uwidth` — display width by UAX #11 plus the zero-width categories
  every terminal adds to it. `char_width` is the exact
  `fn(Int) -> Int` that textwrap-nv's published `WrapWidth` holds,
  which is why it takes no table argument and why the width tables are
  compiled in.
- `ugrapheme` — UAX #29 extended grapheme clusters and word
  boundaries, in two surfaces over one algorithm: a cursor for a caller
  holding the string, and `break_step` for a terminal receiving one
  codepoint at a time.
- `unorm` — NFC, NFD, NFKC, NFKD, with `quick_check` and `compare` as
  first-class answers so the common case — text that is already
  normalised — costs no allocation.
- `ucase` — full case mapping and folding, with the language as a
  parameter because Turkish "i" is a different letter, and with folding
  separated from lowercasing because they answer different questions.
- `uclass` — the thirty general categories behind a `UniData`, and the
  predicates a lexer's inner loop asks compiled in without one.
- `udata` — the table tiering: always-there, asked-for-by-name, and
  parsed-from-bytes-the-host-read.

### Known

- **No dependencies, and the absence is the design.** This package is
  the bottom of the text tier; a dependency here would be one every
  consumer inherits.
- **The device claim covers `uwidth`, `ugrapheme` and `uclass` only.**
  `unorm` and `ucase` are 245 KB of table, which is most of an nRF52's
  flash. A firmware that needs them reaches them through
  `udata.data_from_pack`.
- **At 0.0.1 the embedded probe proves the shape, not the size.** Every
  body is a `todo()`, so no table is in the binary yet. Keeping the
  probe green with the tables in is a cost of the implementation step.
- **`ucase.fold` takes no language**, deliberately: a fold is a
  comparison key, and one that depended on the reader's locale would
  make two systems disagree about whether two strings match. The Turkic
  variant is reachable through `simple_fold`.
