#!/usr/bin/env bash
#
# alloc_scan.sh — the claim that the lookup path never allocates, as a
# command that either passes or names the function that broke it.
#
#     bash tools/alloc_scan.sh [path-to-novo]
#
# `uwidth.char_width` is the `fn(Int) -> Int` textwrap-nv's `WrapWidth`
# holds and a terminal calls it once per character of every line it
# paints; `ugrapheme.break_step` is what a terminal emulator calls once
# per codepoint; `uclass`'s predicates are a lexer's inner loop.  The
# `@tier(embedded)` annotations on all three say they reach no
# allocator — but a tier annotation is checked against a list of
# admitted stdlib entries, not against the emitted code, so this reads
# the emitted code.
#
# `novo build` writes the module's LLVM to `_novo/<name>.ll` before it
# invokes clang, so the IR is there to read.  `--opt=0` keeps the
# functions separate: at the default optimisation level the whole probe
# inlines into `novo_main`, there is nothing left to attribute an
# allocation to, and the assertion would pass by vacuity.
#
# The shape is crypto-nv's, which is where it was worked out.

set -u

PKG="$(cd "$(dirname "$0")/.." && pwd)"
NOVO="${1:-${NOVO:-$HOME/.novo/bin/novo}}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

cp -r "$PKG" "$WORK/pkg"
rm -rf "$WORK/pkg/_novo"

if ! (cd "$WORK/pkg" && timeout 900 "$NOVO" build --opt=0 -o "$WORK/pkg/probe.bin" \
        tests/alloc_probe.nv) > "$WORK/build.log" 2>&1; then
    echo "FAIL the allocation probe does not build"
    grep -E 'error' "$WORK/build.log" | head -5
    exit 1
fi

LL="$WORK/pkg/_novo/alloc_probe.ll"
if [ ! -f "$LL" ]; then
    echo "FAIL no _novo/alloc_probe.ll emitted — nothing was measured"
    exit 1
fi

python3 - "$LL" <<'PY'
import re
import sys

src = open(sys.argv[1], encoding='utf-8', errors='replace').read()
fns = re.compile(r'^define[^\n]*?@([A-Za-z0-9_.]+)\([^\n]*\{\n(.*?)\n\}',
                 re.S | re.M)

# The lookup path: the width rule, the break machine, the predicates and
# the table search all three are written on.
hot = re.compile(r'^novo_user_(uwidth_|uclass_|ugrapheme_|utbl_)')

# The half that is NOT claimed, excluded BY NAME rather than by the scan
# quietly not looking at it.  Each of these carries `@tier(app)` in the
# source and allocates deliberately: a cursor is a boxed struct holding
# the caller's string, `clusters` and `words` build a list, `category`
# and its neighbours reach the tier-two tables through a `UniData`, and
# `utbl`'s packed-blob searches read a `[u8]` the host handed over.
cold = re.compile(r'^novo_user_('
                  r'ugrapheme_(cursor|cursor_at|cursor_next|cursor_advance|nth|'
                  r'clusters|words|next_word|prev_word|is_word_boundary|'
                  r'wb_before|wb_after|ri_run_before|word_kind|pred_of|'
                  r'is_ahletter|is_midletterq|is_midnumq)'
                  r'|uclass_(category|category_abbrev|category_named|'
                  r'cat_index|cat_of_index)'
                  r'|utbl_(pkey|pvalue|pcover|pfind|pfind_pair|bytes_of|'
                  r'utf8_of|str_of|char_of)'
                  r')$')

seen = 0
offenders = []
for m in fns.finditer(src):
    name, body = m.group(1), m.group(2)
    if not hot.match(name) or cold.match(name):
        continue
    seen += 1
    n = len(re.findall(r'call[^\n]*@novo_alloc', body))
    if n:
        offenders.append('%s: %d novo_alloc call(s)' % (name, n))

if seen < 30:
    print('FAIL only %d lookup functions found in the IR — the probe or the '
          'name scheme moved, and this check was measuring nothing' % seen)
    sys.exit(1)
if offenders:
    print('FAIL ' + '; '.join(offenders))
    sys.exit(1)
print('OK %d lookup functions, zero novo_alloc' % seen)
PY
