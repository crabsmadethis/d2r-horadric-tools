# D2S Live Test Plan

Run this on `bazzite-home` from `~/recovered-repos/d2r-horadric-tools`.

The goal is to turn the remaining `.d2s` questions into small, reversible live
experiments. The committed YAMLs create test characters; the forge helper creates
follower-block variants as staging files.

## Prerequisites

1. D2R is fully closed.
2. The repo is on a working branch.
3. Generated game data exists. If imports like `d2r_chargen.data.skills` fail,
   run `d2r-mod extract` first.
4. A private fixture with an active bound demon is available. Either place it at
   `tests/fixtures/marrowbind_demon_b.d2s` or set:

```bash
export D2R_FIXTURES=/path/to/private/d2s-fixtures
```

5. Export the live save directory:

```bash
export SAVES="$(python3 - <<'PY'
from d2r_chargen.config import SAVES
print(SAVES)
PY
)"
printf '%s\n' "$SAVES"
```

Before diagnosing a missing probe character, create one throwaway offline
character in-game and fully exit D2R. Use that character as ground truth for:

- the actual save directory D2R is reading
- the companion-file family D2R expects (`.ctl`, `.key`, `.map`, and usually
  `.ma0`)
- the active character-select category, especially softcore vs hardcore status
  byte behavior

On the 2026-05-08 Bazzite session, a fresh throwaway character named `bbbbb`
appeared under the same `2536520` Proton prefix as the probes and created:

```text
bbbbb.d2s
bbbbb.ctl
bbbbb.key
bbbbb.map
bbbbb.ma0
```

The first staged probes used names like `D2SProbeWl0` and did not appear in the
Offline list even after copied companion files and a matching hardcore/alive
status byte (`0x04`). A same-install lowercase clone of the throwaway character
(`ccccc`) appeared and joined successfully. Single-field clones then showed
class, level, progression, current difficulty, and merc header bytes were not
the visibility blocker. The decisive test was name shape: letter-only names
appeared, while names containing the digit `2` did not.

Use letter-only probe names for live tests. Scanner-clean `.d2s` files with
digits in the embedded character name or filename can be invisible in character
select. After renaming the four probes to `probesorc`, `probenecro`,
`probewlzero`, and `probewldemon`, all four appeared in D2R's Offline list on
Bazzite.

For staging outside the live save directory, set both variables:

```bash
export D2R_SAVES=/tmp/d2s-probe-saves
export D2R_FIXTURES=/tmp/d2r-probe-fixtures
mkdir -p "$D2R_SAVES" "$D2R_FIXTURES"
```

## Probe Characters

Committed under `chars/`:

| File | Character | Purpose |
| --- | --- | --- |
| `probewlzero.yaml` | `probewlzero` | Warlock with Bind Demon skill but no follower payload |
| `probewldemon.yaml` | `probewldemon` | Warlock with copied bound-demon payload |
| `probesorc.yaml` | `probesorc` | Non-warlock baseline for borrowed follower forge test |
| `probenecro.yaml` | `probenecro` | Iron Golem capture test |

All names are 15 bytes or fewer for the fixed name field.

## Step 1: Read-only corpus baseline

```bash
python3 tools/d2s_corpus_scan.py \
  ~/recovered-repos/d2r-horadric-tools \
  ~/SK256-extracted/steamdeck-backup/deck \
  --examples 5
```

Record only aggregate counters in public docs.

## Step 2: Validate and build scanner-clean probes

Start with temp validation:

```bash
python3 -m d2r_chargen validate probewlzero
D2R_FIXTURES=${D2R_FIXTURES:-tests/fixtures} python3 -m d2r_chargen validate probewldemon
python3 -m d2r_chargen validate probesorc
python3 -m d2r_chargen validate probenecro
```

Then build one at a time only when ready to run the live test:

```bash
python3 -m d2r_chargen build probewlzero --force
python3 -m d2r_chargen scan probewlzero
```

Repeat for each character as needed.

Note: the Bazzite staging run has already built scanner-clean `.d2s` files for
all four probe YAMLs under `/tmp/d2s-probe-saves`. This requires regenerated
`d2r_chargen.data.skills` data that preserves blank-`*Id` modded skill rows by
using the Skills.txt row index as the skill id.

If those staged files are promoted manually, copy a complete save family rather
than only the `.d2s`:

1. Fully close D2R.
2. Back up any existing live files with the same base name.
3. Copy the staged `.d2s`.
4. Copy `.ctl`, `.key`, `.map`, and `.ma0` from a known D2R-created offline
   character in the same save directory, renamed to the probe base name.
5. If the probe still does not appear, compare its status byte at `0x14` with a
   fresh in-game throwaway character before assuming the save payload was
   rejected.
6. Confirm the embedded character name and file basename contain letters only.
   Avoid digits such as the `2` in `D2SProbe...`.

Prefer `python3 -m d2r_chargen build <name> --force` against the live save
directory when possible, because `create_new_character()` already copies
template companion files for new characters.

## Step 3: Warlock follower presence test

Build and scan both Warlock variants:

```bash
python3 -m d2r_chargen build probewlzero --force
python3 -m d2r_chargen scan probewlzero

D2R_FIXTURES=${D2R_FIXTURES:-tests/fixtures} python3 -m d2r_chargen build probewldemon --force
python3 -m d2r_chargen scan probewldemon
```

Live observations:

- Can each character enter game?
- Does `probewldemon` spawn or preserve the copied bound demon?
- After save and quit, does the rewritten `.d2s` keep `follower_count=1` and
  exactly 116 trailing payload bytes?

2026-05-08 result: `probewldemon` entered game, the demon was present, and
after save-and-quit the rewritten file remained scanner-clean with
`follower_count=1` and 116 trailing payload bytes.

Post-run aggregate check:

```bash
python3 tools/d2s_corpus_scan.py "$SAVES/probewlzero.d2s" "$SAVES/probewldemon.d2s" --examples 2
```

## Step 4: Cross-class borrowed follower test

Build a clean Sorceress baseline:

```bash
python3 -m d2r_chargen build probesorc --force
python3 -m d2r_chargen scan probesorc
```

Forge a staged copy with a copied demon payload:

```bash
python3 tools/d2s_forge_follower.py \
  "$SAVES/probesorc.d2s" \
  /tmp/probesorc.borrowed-follower.d2s \
  --template-d2s "${D2R_FIXTURES:-tests/fixtures}/marrowbind_demon_b.d2s"

python3 tools/d2s_corpus_scan.py /tmp/probesorc.borrowed-follower.d2s --examples 2
```

Manual promotion for this test only:

```bash
cp "$SAVES/probesorc.d2s" "$SAVES/probesorc.d2s.pre_borrowed_follower_bak"
cp /tmp/probesorc.borrowed-follower.d2s "$SAVES/probesorc.d2s"
```

Live observations:

- Can the Sorceress enter game?
- Is the demon visible or ignored?
- Does waypoint travel still work?
- Does fighting one small pack remain stable?
- After save and quit, does D2R preserve, strip, or rewrite the follower block?

2026-05-08 result: borrowed-follower `probesorc` entered game but no follower
appeared. D2R rewrote the save on exit and stripped the follower block back to
`follower_count=0` with no trailing payload.

Restore baseline after the test:

```bash
cp "$SAVES/probesorc.d2s.pre_borrowed_follower_bak" "$SAVES/probesorc.d2s"
```

## Step 5: Negative follower mismatch test

This intentionally creates a save D2R should reject. Do this only with the
probe character and only after backing it up.

```bash
python3 tools/d2s_forge_follower.py \
  "$SAVES/probesorc.d2s" \
  /tmp/probesorc.invalid-follower.d2s \
  --invalid-count-without-payload

python3 tools/d2s_corpus_scan.py /tmp/probesorc.invalid-follower.d2s --examples 2
```

Expected scanner result: `follower_payload_ok: false`.

Expected live result after manual promotion: failed to join game. Restore the
backup immediately afterward.

## Step 6: Iron Golem fixture capture

Build the Necromancer probe:

```bash
python3 -m d2r_chargen build probenecro --force
python3 -m d2r_chargen scan probenecro
```

Live steps:

1. Enter game with `probenecro`.
2. Create an Iron Golem from a simple vendor item.
3. Save and quit.
4. Fully exit D2R.
5. Copy `probenecro.d2s` to a private fixture area.
6. Run `python3 tools/d2s_corpus_scan.py <private fixture> --examples 1`.

Expected research result: the first local example with `has_golem_byte=1`, which
can anchor the `kf 01 <item>` layout.

2026-05-08 result: after creating an Iron Golem on `probenecro`, D2R rewrote
the save with `has_golem_byte=1`, `kf_to_lf_gap=58`, and 55 bytes of golem item
payload before `lf`.

2026-05-08 persistence result: after fully reloading `probenecro`, the Iron
Golem was still present and save-and-quit preserved the same 55-byte golem
payload (`sha1=2f582d487d12a70b8c5cdc1da3e371b2c302c390`).

Second reload on 2026-05-08 still showed the Iron Golem and left
`probenecro.d2s` unchanged on disk with the same payload hash.
