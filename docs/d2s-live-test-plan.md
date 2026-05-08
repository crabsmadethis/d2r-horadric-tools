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

The staged probes were scanner-clean as bare `.d2s` files, but did not appear in
the Offline list. Adding copied companion files and matching the throwaway
character's hardcore/alive status byte (`0x04`) was still insufficient in that
session. Treat this as an unresolved character-select visibility rule, not as a
payload rejection.

Next diagnostic: with D2R fully closed, clone the exact same-install throwaway
file family to a simple lowercase name, patch only the `.d2s` embedded name and
checksum, and relaunch. If the clone appears, the probe payload/header differs
from a displayable D2R-written save. If the clone does not appear, D2R likely
uses another character-list cache or index beyond the visible save family.

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
| `D2SProbeWl0.yaml` | `D2SProbeWl0` | Warlock with Bind Demon skill but no follower payload |
| `D2SProbeWlD.yaml` | `D2SProbeWlD` | Warlock with copied bound-demon payload |
| `D2SProbeSorc.yaml` | `D2SProbeSorc` | Non-warlock baseline for borrowed follower forge test |
| `D2SProbeNecro.yaml` | `D2SProbeNecro` | Iron Golem capture test |

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
python3 -m d2r_chargen validate D2SProbeWl0
D2R_FIXTURES=${D2R_FIXTURES:-tests/fixtures} python3 -m d2r_chargen validate D2SProbeWlD
python3 -m d2r_chargen validate D2SProbeSorc
python3 -m d2r_chargen validate D2SProbeNecro
```

Then build one at a time only when ready to run the live test:

```bash
python3 -m d2r_chargen build D2SProbeWl0 --force
python3 -m d2r_chargen scan D2SProbeWl0
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
6. If it still does not appear, run the lowercase clone diagnostic above before
   changing any probe payload bytes.

Prefer `python3 -m d2r_chargen build <name> --force` against the live save
directory when possible, because `create_new_character()` already copies
template companion files for new characters.

## Step 3: Warlock follower presence test

Build and scan both Warlock variants:

```bash
python3 -m d2r_chargen build D2SProbeWl0 --force
python3 -m d2r_chargen scan D2SProbeWl0

D2R_FIXTURES=${D2R_FIXTURES:-tests/fixtures} python3 -m d2r_chargen build D2SProbeWlD --force
python3 -m d2r_chargen scan D2SProbeWlD
```

Live observations:

- Can each character enter game?
- Does `D2SProbeWlD` spawn or preserve the copied bound demon?
- After save and quit, does the rewritten `.d2s` keep `follower_count=1` and
  exactly 116 trailing payload bytes?

Post-run aggregate check:

```bash
python3 tools/d2s_corpus_scan.py "$SAVES/D2SProbeWl0.d2s" "$SAVES/D2SProbeWlD.d2s" --examples 2
```

## Step 4: Cross-class borrowed follower test

Build a clean Sorceress baseline:

```bash
python3 -m d2r_chargen build D2SProbeSorc --force
python3 -m d2r_chargen scan D2SProbeSorc
```

Forge a staged copy with a copied demon payload:

```bash
python3 tools/d2s_forge_follower.py \
  "$SAVES/D2SProbeSorc.d2s" \
  /tmp/D2SProbeSorc.borrowed-follower.d2s \
  --template-d2s "${D2R_FIXTURES:-tests/fixtures}/marrowbind_demon_b.d2s"

python3 tools/d2s_corpus_scan.py /tmp/D2SProbeSorc.borrowed-follower.d2s --examples 2
```

Manual promotion for this test only:

```bash
cp "$SAVES/D2SProbeSorc.d2s" "$SAVES/D2SProbeSorc.d2s.pre_borrowed_follower_bak"
cp /tmp/D2SProbeSorc.borrowed-follower.d2s "$SAVES/D2SProbeSorc.d2s"
```

Live observations:

- Can the Sorceress enter game?
- Is the demon visible or ignored?
- Does waypoint travel still work?
- Does fighting one small pack remain stable?
- After save and quit, does D2R preserve, strip, or rewrite the follower block?

Restore baseline after the test:

```bash
cp "$SAVES/D2SProbeSorc.d2s.pre_borrowed_follower_bak" "$SAVES/D2SProbeSorc.d2s"
```

## Step 5: Negative follower mismatch test

This intentionally creates a save D2R should reject. Do this only with the
probe character and only after backing it up.

```bash
python3 tools/d2s_forge_follower.py \
  "$SAVES/D2SProbeSorc.d2s" \
  /tmp/D2SProbeSorc.invalid-follower.d2s \
  --invalid-count-without-payload

python3 tools/d2s_corpus_scan.py /tmp/D2SProbeSorc.invalid-follower.d2s --examples 2
```

Expected scanner result: `follower_payload_ok: false`.

Expected live result after manual promotion: failed to join game. Restore the
backup immediately afterward.

## Step 6: Iron Golem fixture capture

Build the Necromancer probe:

```bash
python3 -m d2r_chargen build D2SProbeNecro --force
python3 -m d2r_chargen scan D2SProbeNecro
```

Live steps:

1. Enter game with `D2SProbeNecro`.
2. Create an Iron Golem from a simple vendor item.
3. Save and quit.
4. Fully exit D2R.
5. Copy `D2SProbeNecro.d2s` to a private fixture area.
6. Run `python3 tools/d2s_corpus_scan.py <private fixture> --examples 1`.

Expected research result: the first local example with `has_golem_byte=1`, which
can anchor the `kf 01 <item>` layout.
