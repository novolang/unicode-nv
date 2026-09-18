#!/usr/bin/env python3
"""Generate unicode-nv's tables from the Unicode Character Database.

    python3 tools/gen_tables.py <ucd-directory> [--src src]

<ucd-directory> holds the UCD files, downloaded from
https://www.unicode.org/Public/<version>/ucd/ :

    UnicodeData.txt            CompositionExclusions.txt
    EastAsianWidth.txt         DerivedNormalizationProps.txt
    PropList.txt               CaseFolding.txt
    DerivedCoreProperties.txt  SpecialCasing.txt
    auxiliary/GraphemeBreakProperty.txt
    auxiliary/WordBreakProperty.txt
    emoji/emoji-data.txt

The raw files are not committed.  They are 8 MB of ASCII that the
Consortium already publishes, and a copy in this repository would be a
second original.  This script is committed instead, so every table
under src/ can be reproduced from the version named in UNICODE_VERSION
by one command.

Every table is emitted as a string literal rather than as a list.  A
`const` list is inlined at every use site (docs/language/guide.md,
"Constants"), which for a table of four thousand entries is four
thousand words copied per call site.  A `const` Str is a pointer to
static data, `str.byte_at_or` reads it with a bounds check and a load,
and both `str.len` and `str.byte_at_or` are admitted under
`@tier(embedded)`.  So the same table serves the host and a Cortex-M
with no allocator, and every table below is a byte string read through
`utbl`.

A table has one of two shapes.

  A covering table is a sorted run of `(start, value)` entries, each
  one holding until the next one starts.  The first entry starts at
  U+0000, so every codepoint is covered and the search never misses.
  It is used where a property has a value everywhere: width, the break
  classes, the predicate bits, the general category, the combining
  class and the quick-check bits.

  A keyed table is a sorted run of `(key, value)` entries searched for
  an exact match.  It is used where most codepoints have no entry at
  all: the case mappings, the decompositions and the compositions.

Keys are three bytes big-endian, which covers U+10FFFF.  A value is
one, two or three bytes big-endian, and each table's entry size is
emitted beside it.
"""

import os
import sys

# ── the property vocabularies, in the order the Novo enums declare ───
#
# The index emitted here is the enum's declaration index, so `uclass`
# and `uwidth` turn a table byte into an enum arm with one `match` and
# no lookup table of their own.  Changing an enum's declaration order
# without changing this list would silently relabel every codepoint.

EAW = ["N", "Na", "W", "F", "H", "A"]

CATEGORIES = [
    "Lu", "Ll", "Lt", "Lm", "Lo",
    "Mn", "Mc", "Me",
    "Nd", "Nl", "No",
    "Pc", "Pd", "Ps", "Pe", "Pi", "Pf", "Po",
    "Sm", "Sc", "Sk", "So",
    "Zs", "Zl", "Zp",
    "Cc", "Cf", "Cs", "Co", "Cn",
]

GCB = [
    "Other", "CR", "LF", "Control", "Extend", "ZWJ", "Regional_Indicator",
    "Prepend", "SpacingMark", "L", "V", "T", "LV", "LVT",
]

WB = [
    "Other", "CR", "LF", "Newline", "Extend", "ZWJ", "Regional_Indicator",
    "Format", "Katakana", "Hebrew_Letter", "ALetter", "Single_Quote",
    "Double_Quote", "MidNumLet", "MidLetter", "MidNum", "Numeric",
    "ExtendNumLet", "WSegSpace",
]

INCB = ["None", "Linker", "Consonant", "Extend"]

MAX_CP = 0x10FFFF


# ── reading the UCD ──────────────────────────────────────────────────

def fields(line):
    """The semicolon-separated fields of a UCD line, comment stripped."""
    line = line.split("#", 1)[0].strip()
    if not line:
        return None
    return [f.strip() for f in line.split(";")]


def read_ranges(path, value_index=1, filter_value=None):
    """Every `(first, last, value)` a range-per-line UCD file lists."""
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            f = fields(line)
            if not f or len(f) <= value_index:
                continue
            cps = f[0]
            if ".." in cps:
                first, last = cps.split("..")
            else:
                first = last = cps
            value = f[value_index]
            if filter_value is not None and value != filter_value:
                continue
            out.append((int(first, 16), int(last, 16), value))
    return out


def read_prop_set(path, name, value_index=1):
    """The set of codepoints a file gives property `name`."""
    s = set()
    for first, last, _ in read_ranges(path, value_index, name):
        s.update(range(first, last + 1))
    return s


def read_unicode_data(path):
    """UnicodeData.txt as a dict, with the First/Last ranges expanded.

    A block such as the CJK ideographs is written as two lines, `<...,
    First>` and `<..., Last>`, rather than as forty thousand.  Every
    codepoint between them carries the First line's properties, which
    is what makes the category table say Lo across the whole block.
    """
    rows = {}
    pending = None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            f = line.rstrip("\n").split(";")
            if len(f) < 15:
                continue
            cp = int(f[0], 16)
            name = f[1]
            if name.endswith(", First>"):
                pending = (cp, f)
                continue
            if name.endswith(", Last>") and pending is not None:
                start, pf = pending
                for c in range(start, cp + 1):
                    rows[c] = pf
                pending = None
                continue
            rows[cp] = f
    return rows


# ── encoding ─────────────────────────────────────────────────────────

def be(value, width):
    """`value` as `width` big-endian bytes."""
    if value < 0 or value >= (1 << (8 * width)):
        raise ValueError("value %d does not fit in %d bytes" % (value, width))
    return bytes((value >> (8 * (width - 1 - i))) & 0xFF for i in range(width))


def covering(values, default, vwidth):
    """A covering table over `values`, a dict of codepoint to value.

    Runs of equal value collapse to one entry, so the table's size is
    the number of times the property changes rather than the number of
    codepoints — which is why a property defined over 1.1 million
    codepoints fits in a few kilobytes.
    """
    out = bytearray()
    entries = 0
    previous = None
    for cp in range(0, MAX_CP + 1):
        v = values.get(cp, default)
        if v != previous:
            out += be(cp, 3) + be(v, vwidth)
            entries += 1
            previous = v
    return bytes(out), entries


def keyed(items, vwidth):
    """A keyed table: `items` is a sorted list of `(key, value)`."""
    out = bytearray()
    for key, value in items:
        out += be(key, 3) + be(value, vwidth)
    return bytes(out)


def literal(data):
    """`data` as a Novo string literal, one `\\xNN` escape per byte.

    Every byte is escaped rather than only the ones that need it: a
    table is not text, a reader who opens the file is looking at a
    generated blob either way, and an alphabet with no special cases
    cannot be got wrong.
    """
    return '"' + "".join("\\x%02X" % b for b in data) + '"'


class Module:
    """A generated Novo module, accumulated and written once."""

    def __init__(self, name, headline, note):
        self.name = name
        self.lines = [
            "// %s.nv — %s" % (name, headline),
            "//",
            "// Generated by tools/gen_tables.py from the Unicode %s"
            % UNICODE_VERSION,
            "// Character Database.  Do not edit it by hand.  Regenerate it",
            "// with",
            "//",
            "//     python3 tools/gen_tables.py <ucd-directory>",
            "//",
        ]
        self.lines += ["// " + l if l else "//" for l in note.strip().split("\n")]
        self.lines.append("")
        self.sizes = []
        self.total = 0
        self.bmp = 0

    def table(self, name, data, esz, comment, keyed=True):
        for l in comment.strip().split("\n"):
            self.lines.append("// " + l if l else "//")
        self.lines.append("const %s_ESZ = %d" % (name, esz))
        self.lines.append("const %s = %s" % (name, literal(data)))
        self.lines.append("")
        self.sizes.append((name, len(data), len(data) // esz))
        self.total += len(data)
        if keyed:
            at = 0
            while at + esz <= len(data):
                if int.from_bytes(data[at:at + 3], "big") > 0xFFFF:
                    break
                at += esz
            self.bmp += at
        else:
            self.bmp += len(data)

    def number(self, name, value, comment):
        for l in comment.strip().split("\n"):
            self.lines.append("// " + l if l else "//")
        self.lines.append("const %s = %d" % (name, value))
        self.lines.append("")

    def totals(self):
        """The two numbers `udata.table_bytes` answers with."""
        self.number(
            "BYTES", self.total,
            """
How many bytes of table this module holds.  `udata` sums these to
answer `UniData.table_bytes`, so the number a caller sizing a firmware
image reads is generated from the tables rather than typed.
""",
        )
        self.number(
            "BMP_BYTES", self.bmp,
            """
How much of that covers the Basic Multilingual Plane, which is the
share a `udata.data_compact()` handle can speak for.
""",
        )

    def write(self, src):
        with open(os.path.join(src, self.name + ".nv"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(self.lines).rstrip("\n") + "\n")
        total = sum(n for _, n, _ in self.sizes)
        print("%-10s %7d bytes" % (self.name + ".nv", total))
        for name, n, entries in self.sizes:
            print("    %-12s %7d bytes  %6d entries" % (name, n, entries))
        return total


# ── the tables that are always compiled in ───────────────────────────

def gen_core(ucd, rows):
    """Width, the UAX #29 break classes, and the lexer predicates.

    These three are compiled in unconditionally and take no `UniData`,
    because `uwidth.char_width` has to be the bare `fn(Int) -> Int`
    textwrap-nv's `WrapWidth` holds.  Together they are the three
    modules that build for a device.
    """
    m = Module(
        "udbcore",
        "the tables that are always compiled in.",
        """
`uwidth`, `ugrapheme` and `uclass`'s predicates read these and take no
data handle, so they cost a program nothing to reach and run under
`@tier(embedded)`.  The three tables behind a `UniData` are in
`udbcat`, `udbcase` and `udbnorm`.
""",
    )

    # ── width ───────────────────────────────────────────────────────
    #
    # East_Asian_Width decides two cells; the general categories Mn, Me
    # and Cf decide none.  UAX #11 covers only the first, so the second
    # is added here — a package that did not would measure every
    # accented word one cell too long per mark.
    eaw = {}
    for first, last, v in read_ranges(os.path.join(ucd, "EastAsianWidth.txt")):
        for cp in range(first, last + 1):
            eaw[cp] = EAW.index(v)
    # The unassigned codepoints of the CJK blocks and of planes 2 and 3
    # default to W rather than to N — EastAsianWidth.txt's own header
    # says so, and a terminal draws a future ideograph in two cells.
    for first, last in [
        (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF),
        (0x20000, 0x2FFFD), (0x30000, 0x3FFFD),
    ]:
        for cp in range(first, last + 1):
            eaw.setdefault(cp, EAW.index("W"))

    zero = set()
    for cp, f in rows.items():
        if f[2] in ("Mn", "Me", "Cf"):
            zero.add(cp)
    # U+200B ZERO WIDTH SPACE is Zs, not Cf, and is the one codepoint
    # whose name is its width.  The Hangul fillers are Lo and occupy no
    # cell either: a jungseong filler is how a partial syllable is
    # written and a terminal draws nothing for it.
    zero.add(0x200B)
    zero.update(range(0x1160, 0x11A8))       # Hangul jungseong
    zero.update([0x115F, 0x3164, 0xFFA0])    # the choseong and halfwidth fillers
    # U+00AD SOFT HYPHEN is Cf but every terminal draws it as one cell.
    zero.discard(0x00AD)

    width = {}
    for cp in set(eaw) | zero:
        v = eaw.get(cp, EAW.index("N"))
        if cp in zero:
            v |= 0x08
        width[cp] = v
    data, n = covering(width, EAW.index("N"), 1)
    m.table(
        "WIDTH", data, 4,
        """
Display width, covering.  The value byte is the East_Asian_Width index
in bits 0..2, which is the declaration order of `uwidth.UniEastAsian`,
and bit 3 is set when the codepoint occupies no cell at all.
""",
    )

    # ── the break classes ───────────────────────────────────────────
    gcb = {}
    for first, last, v in read_ranges(
            os.path.join(ucd, "auxiliary", "GraphemeBreakProperty.txt")):
        for cp in range(first, last + 1):
            gcb[cp] = GCB.index(v)
    wb = {}
    for first, last, v in read_ranges(
            os.path.join(ucd, "auxiliary", "WordBreakProperty.txt")):
        for cp in range(first, last + 1):
            wb[cp] = WB.index(v)
    extpict = read_prop_set(os.path.join(ucd, "emoji", "emoji-data.txt"),
                            "Extended_Pictographic")
    incb = {}
    for first, last, v in read_ranges(
            os.path.join(ucd, "DerivedCoreProperties.txt"), 2):
        f2 = v
        if f2 in ("Linker", "Consonant", "Extend"):
            for cp in range(first, last + 1):
                incb[cp] = INCB.index(f2)

    brk = {}
    for cp in set(gcb) | set(wb) | extpict | set(incb):
        v = gcb.get(cp, 0) | (wb.get(cp, 0) << 5)
        if cp in extpict:
            v |= 1 << 10
        v |= incb.get(cp, 0) << 11
        brk[cp] = v
    data, n = covering(brk, 0, 2)
    m.table(
        "BREAK", data, 5,
        """
The UAX #29 break classes, covering.  The two value bytes hold
Grapheme_Cluster_Break in bits 0..4, Word_Break in bits 5..9,
Extended_Pictographic in bit 10 and Indic_Conjunct_Break in bits
11..12, each in the declaration order of `ugrapheme`'s own tables.
One table rather than four, because the four properties change at
nearly the same codepoints, so four tables would cost four searches
and four times the boundaries.
""",
    )

    # ── the lexer predicates ────────────────────────────────────────
    dcp = os.path.join(ucd, "DerivedCoreProperties.txt")
    props = {
        "upper": read_prop_set(dcp, "Uppercase"),
        "lower": read_prop_set(dcp, "Lowercase"),
        "ids": read_prop_set(dcp, "ID_Start"),
        "idc": read_prop_set(dcp, "ID_Continue"),
        "xids": read_prop_set(dcp, "XID_Start"),
        "xidc": read_prop_set(dcp, "XID_Continue"),
    }
    white = read_prop_set(os.path.join(ucd, "PropList.txt"), "White_Space")

    pred = {}
    interesting = set(rows) | white
    for k in props.values():
        interesting |= k
    for cp in interesting:
        cat = rows[cp][2] if cp in rows else "Cn"
        v = 0
        if cat[0] == "L":
            v |= 1 << 0
        if cat == "Nd":
            v |= 1 << 1
        if cat[0] == "N":
            v |= 1 << 2
        if cp in white:
            v |= 1 << 3
        if cat == "Cc":
            v |= 1 << 4
        if cat[0] == "M":
            v |= 1 << 5
        if cat[0] == "P":
            v |= 1 << 6
        if cat[0] == "S":
            v |= 1 << 7
        if cp in props["upper"]:
            v |= 1 << 8
        if cp in props["lower"]:
            v |= 1 << 9
        if cp in props["ids"]:
            v |= 1 << 10
        if cp in props["idc"]:
            v |= 1 << 11
        if cp in props["xids"]:
            v |= 1 << 12
        if cp in props["xidc"]:
            v |= 1 << 13
        if v:
            pred[cp] = v
    data, n = covering(pred, 0, 2)
    m.table(
        "PRED", data, 5,
        """
The predicates a lexer asks in its inner loop, covering.  One bit each,
in this order: letter, decimal number, any number, White_Space,
control, mark, punctuation, symbol, Uppercase, Lowercase, ID_Start,
ID_Continue, XID_Start, XID_Continue.

Uppercase and Lowercase are the properties rather than the Lu and Ll
categories.  They also carry the Other_Uppercase codepoints, which is
the set a caseless comparison has to agree with.  White_Space is the
property too, for the reason `uclass.is_whitespace` gives.  Every
implementation that derives it from the Z categories gets a different
answer.
""",
    )
    return m


# ── the general category ─────────────────────────────────────────────

def gen_cat(rows):
    m = Module(
        "udbcat",
        "the general category of every codepoint.",
        """
Reached through `udata.UniData`.  `uclass.category` is the one
function that needs the whole classification rather than the handful
of bits `udbcore.PRED` carries, and it is why that function takes a
data handle where the predicates beside it do not.
""",
    )
    cat = {}
    for cp, f in rows.items():
        cat[cp] = CATEGORIES.index(f[2])
    # A surrogate is Cs and is listed in UnicodeData.txt as a First/Last
    # block, so the expansion above already covers it.
    data, n = covering(cat, CATEGORIES.index("Cn"), 1)
    m.table(
        "CAT", data, 4,
        """
The general category, covering.  The value byte is the declaration
index of `uclass.UniCategory`, so the lookup is one `match` and no
second table.
""",
    )
    return m


# ── case mapping ─────────────────────────────────────────────────────

def gen_case(ucd, rows):
    m = Module(
        "udbcase",
        "case mapping, special casing and case folding.",
        """
Reached through `udata.UniData`.

The simple and the full mappings are two tables, because they answer
two different questions.  A simple mapping is one codepoint to one
codepoint, and it is what a caller walking codepoints wants.  A full
mapping may be three codepoints, which is what "SS" and "FFI" are, and
cannot be expressed in the first table at all.  Most codepoints that
have case have only the simple form, so the full table holds the
hundred-odd exceptions rather than a copy of everything.
""",
    )

    simple = {}

    def slot(cp):
        return simple.setdefault(cp, [0, 0, 0, 0])

    for cp, f in rows.items():
        upper, lower, title = f[12], f[13], f[14]
        if lower:
            slot(cp)[0] = int(lower, 16)
        if upper:
            slot(cp)[1] = int(upper, 16)
        if title:
            slot(cp)[2] = int(title, 16)
        elif upper:
            # UnicodeData.txt leaves the titlecase field empty when it
            # equals the uppercase mapping, which is the usual case.
            slot(cp)[2] = int(upper, 16)

    full = {}

    def full_slot(cp):
        return full.setdefault(cp, [None, None, None, None])

    # CaseFolding.txt: C is the common fold, S the simple-only fold, F
    # the full one.  T is the Turkic variant, which `ucase.fold` does
    # not take — a fold is a comparison key and a key that depended on
    # the reader's locale would make two systems disagree.
    with open(os.path.join(ucd, "CaseFolding.txt"), encoding="utf-8") as fh:
        for line in fh:
            f = fields(line)
            if not f or len(f) < 3:
                continue
            cp, status, mapping = int(f[0], 16), f[1], f[2]
            cps = [int(x, 16) for x in mapping.split()]
            if status in ("C", "S"):
                slot(cp)[3] = cps[0]
            elif status == "F":
                full_slot(cp)[3] = cps

    # SpecialCasing.txt: the unconditional lines only.  The conditional
    # ones are the language rules and the final-sigma rule, which are
    # context and live in `ucase` as code rather than as a table.
    with open(os.path.join(ucd, "SpecialCasing.txt"), encoding="utf-8") as fh:
        for line in fh:
            f = fields(line)
            if not f or len(f) < 4:
                continue
            if len(f) >= 5 and f[4]:
                continue
            cp = int(f[0], 16)
            lower = [int(x, 16) for x in f[1].split()]
            title = [int(x, 16) for x in f[2].split()]
            upper = [int(x, 16) for x in f[3].split()]
            s = full_slot(cp)
            if len(lower) != 1 or lower[0] != cp:
                s[0] = lower
            if len(upper) != 1 or upper[0] != cp:
                s[1] = upper
            if len(title) != 1 or title[0] != cp:
                s[2] = title

    data = bytearray()
    for cp in sorted(simple):
        lower, upper, title, fold = simple[cp]
        data += be(cp, 3) + be(lower, 3) + be(upper, 3) + be(title, 3) + be(fold, 3)
    m.table(
        "SIMPLE", bytes(data), 15,
        """
The one-codepoint mappings, keyed.  Each entry is the codepoint and
then its lowercase, uppercase, titlecase and folded forms, three bytes
each, with U+0000 meaning "no mapping".  U+0000 is never a mapping
target, so the sentinel costs no real value.
""",
    )

    pool = bytearray()
    index = {}

    def intern(cps):
        key = tuple(cps)
        if key not in index:
            index[key] = len(pool) // 3
            for c in cps:
                pool.extend(be(c, 3))
        return index[key]

    data = bytearray()
    for cp in sorted(full):
        entry = bytearray(be(cp, 3))
        for cps in full[cp]:
            if cps is None:
                entry += be(0, 2) + be(0, 1)
            else:
                entry += be(intern(cps), 2) + be(len(cps), 1)
        data += entry
    m.table(
        "FULL", bytes(data), 15,
        """
The mappings that are not one codepoint to one codepoint, keyed.  Each
entry is the codepoint and then four `(offset, length)` pairs into
FULLPOOL, in the order lowercase, uppercase, titlecase and folded.  A
length of zero means the simple mapping is the whole answer.
""",
    )
    m.table(
        "FULLPOOL", bytes(pool), 3,
        "The codepoints FULL indexes into, three bytes each.",
        keyed=False,
    )

    dcp = os.path.join(ucd, "DerivedCoreProperties.txt")
    cased = read_prop_set(dcp, "Cased")
    cwcf = read_prop_set(dcp, "Changes_When_Casefolded")
    ignorable = read_prop_set(dcp, "Case_Ignorable")
    dotted = read_prop_set(os.path.join(ucd, "PropList.txt"), "Soft_Dotted")
    flags = {}
    for cp in cased | cwcf | ignorable | dotted:
        v = 0
        if cp in cased:
            v |= 1
        if cp in cwcf:
            v |= 2
        if cp in ignorable:
            v |= 4
        if cp in dotted:
            v |= 8
        flags[cp] = v
    data, n = covering(flags, 0, 1)
    m.table(
        "CASEP", data, 4,
        """
Cased, Changes_When_Casefolded, Case_Ignorable and Soft_Dotted,
covering, one bit each.  The last two are not published as functions.
They are what SpecialCasing.txt's conditions are written over.
Final_Sigma and After_I skip the case-ignorable characters, and
After_Soft_Dotted is the whole of the Lithuanian uppercase rule, and
those conditions live in `ucase`.
""",
    )
    return m


# ── normalisation ────────────────────────────────────────────────────

def gen_norm(ucd, rows):
    m = Module(
        "udbnorm",
        "the decompositions, the compositions and the combining classes.",
        """
Reached through `udata.UniData`, and the largest tables in the
package.

Hangul is not here.  UAX #15 § 3.12 gives the syllables' composition
and decomposition as arithmetic over the codepoint, so eleven thousand
entries are four lines of code in `unorm` instead.  A table would
answer the same and cost 60 KB.
""",
    )

    ccc = {}
    for cp, f in rows.items():
        v = int(f[3])
        if v:
            ccc[cp] = v
    data, n = covering(ccc, 0, 1)
    m.table(
        "CCC", data, 4,
        "Canonical_Combining_Class, covering.  Zero is a starter.",
    )

    pool = bytearray()
    index = {}

    def intern(cps):
        key = tuple(cps)
        if key not in index:
            index[key] = len(pool) // 3
            for c in cps:
                pool.extend(be(c, 3))
        return index[key]

    decomp = {}
    for cp, f in rows.items():
        d = f[5].strip()
        if not d:
            continue
        compat = d.startswith("<")
        if compat:
            d = d.split(">", 1)[1]
        cps = [int(x, 16) for x in d.split()]
        decomp[cp] = (compat, cps)

    data = bytearray()
    for cp in sorted(decomp):
        compat, cps = decomp[cp]
        data += be(cp, 3) + be(1 if compat else 0, 1) \
            + be(intern(cps), 2) + be(len(cps), 1)
    m.table(
        "DECOMP", bytes(data), 7,
        """
The one-step decomposition mappings, keyed.  Each entry is the
codepoint, a flag byte that is 1 for a compatibility mapping and 0 for
a canonical one, and an `(offset, length)` into DECOMPPOOL.  One step
rather than the recursive form.  `unorm.decompose_char` recurses, and
storing the closure would repeat every shared tail.
""",
    )
    m.table(
        "DECOMPPOOL", bytes(pool), 3,
        "The codepoints DECOMP indexes into, three bytes each.",
        keyed=False,
    )

    exclusions = set()
    for first, last, _ in read_ranges(
            os.path.join(ucd, "CompositionExclusions.txt"), 0):
        exclusions.update(range(first, last + 1))
    for first, last, _ in read_ranges(
            os.path.join(ucd, "DerivedNormalizationProps.txt"), 1,
            "Full_Composition_Exclusion"):
        exclusions.update(range(first, last + 1))

    pairs = []
    for cp, (compat, cps) in decomp.items():
        if compat or len(cps) != 2 or cp in exclusions:
            continue
        pairs.append((cps[0], cps[1], cp))
    pairs.sort()
    data = bytearray()
    for starter, combining, composite in pairs:
        data += be(starter, 3) + be(combining, 3) + be(composite, 3)
    m.table(
        "COMP", bytes(data), 9,
        """
The primary composites, keyed on the pair.  Each entry is the starter,
the combining codepoint and what they compose to, sorted so that one
search over nine-byte entries finds a pair.  A composite that
Full_Composition_Exclusion names is absent, which is why this is a
table of its own rather than DECOMP read backwards.
""",
    )

    qc = {}
    dnp = os.path.join(ucd, "DerivedNormalizationProps.txt")
    for i, name in enumerate(["NFD_QC", "NFC_QC", "NFKD_QC", "NFKC_QC"]):
        for first, last, _ in read_ranges(dnp, 1, name):
            pass
        with open(dnp, encoding="utf-8") as fh:
            for line in fh:
                f = fields(line)
                if not f or len(f) < 3 or f[1] != name:
                    continue
                v = {"N": 1, "M": 2}[f[2]]
                cps = f[0]
                first, last = (cps.split("..") + [cps.split("..")[0]])[:2] \
                    if ".." in cps else (cps, cps)
                for cp in range(int(first, 16), int(last, 16) + 1):
                    qc[cp] = qc.get(cp, 0) | (v << (2 * i))
    data, n = covering(qc, 0, 1)
    m.table(
        "QC", data, 4,
        """
The four quick-check properties, covering, two bits each in the order
NFD, NFC, NFKD, NFKC.  0 is Yes, 1 is No and 2 is Maybe.  This is the
table `unorm.quick_check` reads, and reading it is why that function
can answer without allocating.
""",
    )
    return m


def main():
    if len(sys.argv) < 2:
        sys.stderr.write(__doc__)
        return 2
    ucd = sys.argv[1]
    src = "src"
    if "--src" in sys.argv:
        src = sys.argv[sys.argv.index("--src") + 1]

    global UNICODE_VERSION
    UNICODE_VERSION = None
    with open(os.path.join(ucd, "EastAsianWidth.txt"), encoding="utf-8") as fh:
        head = fh.readline()
        UNICODE_VERSION = head.split("-", 1)[1].rsplit(".txt", 1)[0].strip()
    print("Unicode %s, from %s" % (UNICODE_VERSION, ucd))

    rows = read_unicode_data(os.path.join(ucd, "UnicodeData.txt"))
    total = 0
    for m in [gen_core(ucd, rows), gen_cat(rows),
              gen_case(ucd, rows), gen_norm(ucd, rows)]:
        m.totals()
        total += m.write(src)
    print("%-10s %7d bytes of table in total" % ("", total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
