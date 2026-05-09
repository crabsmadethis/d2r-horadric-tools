# D2S Live Test Plan

Public tooling lane. This plan keeps live `.d2s` validation reproducible without
committing private saves, raw save corpora, Steam paths, Proton paths, or
machine-local calibration data.

Use live D2R only when scanner and tool-level checks cannot answer the question.
Each live recipe follows the same safety loop:

1. Back up the current live save family outside the public repo.
2. Build or forge into a staging directory first.
3. Scan the staged file before promotion.
4. Fully close D2R, promote one probe, relaunch, and record the live observation.
5. Fully exit D2R and run a post-run scan before drawing conclusions.

## Prerequisites

- Work from the public repo root:

```bash
export D2R_PUBLIC_REPO="/path/to/d2r-horadric-tools-current"
cd "$D2R_PUBLIC_REPO"
```

- Generated game data exists. If imports such as `d2r_chargen.data.skills`
  fail, run `d2r-mod extract` against the user's local D2R install.

- Live runs have explicit private paths supplied by environment variables. Do
  not write these paths into committed fixtures or docs as concrete machine
  locations.

```bash
export D2R_LIVE_SAVES="/path/to/live/offline-save-directory"
export D2R_STAGE="/path/to/disposable/staging-save-directory"
export D2R_BACKUP_DIR="/path/to/private/backup-directory"
mkdir -p "$D2R_STAGE" "$D2R_BACKUP_DIR"
```

- Fixture-dependent recipes set private fixture inputs explicitly:

```bash
export D2R_FIXTURES="/path/to/private/d2s-fixtures"
export D2R_DEMON_FIXTURE="$D2R_FIXTURES/marrowbind_demon_b.d2s"
```

- Before diagnosing a missing probe character, create one throwaway Offline
  character in-game, fully exit D2R, and use that character as ground truth for:

  - the live save directory D2R is reading
  - the companion-file family D2R expects, usually `.d2s`, `.ctl`, `.key`,
    `.map`, and `.ma0`
  - the active character-select category, especially softcore vs. hardcore
    status-byte behavior

- Use letter-only probe names. Recent live validation showed scanner-clean
  saves with digits in the embedded character name or filename can be invisible
  in character select.

## Probe Characters

The public probe YAMLs are committed under `chars/`:

| File | Character | Purpose |
| --- | --- | --- |
| `probewlzero.yaml` | `probewlzero` | Warlock with Bind Demon skill but no follower payload |
| `probewldemon.yaml` | `probewldemon` | Warlock with copied bound-demon payload |
| `probesorc.yaml` | `probesorc` | Non-warlock baseline for borrowed-follower regression |
| `probenecro.yaml` | `probenecro` | Iron Golem capture and parser regression |

All probe names are letter-only and 15 bytes or fewer for the fixed name field.

## Repeatable Recipes

### Read-Only Corpus Baseline

Use this only with private corpus paths supplied at runtime. Record aggregate
counters only in public docs.

```bash
export D2R_CORPUS_ROOT="/path/to/private/corpus"
python3 tools/d2s_corpus_scan.py "$D2R_CORPUS_ROOT" --examples 5
```

### Validate, Build, and Scan Probes

Build into staging first. Promote to the live save directory only after the
scanner passes.

```bash
export D2R_SAVES="$D2R_STAGE"

python3 -m d2r_chargen validate probewlzero
python3 -m d2r_chargen validate probesorc
python3 -m d2r_chargen validate probenecro
D2R_FIXTURES="$D2R_FIXTURES" python3 -m d2r_chargen validate probewldemon

python3 -m d2r_chargen build probewlzero --force
python3 -m d2r_chargen scan probewlzero
```

Repeat the build and scan pair for only the probe being tested. Do not stack
multiple risky save changes before scanning.

### Complete Save-Family Promotion

Use this for manual promotion when not using the tool's live-save build path.
The live game should be fully closed before every copy.

```bash
probe="probewlzero"
template="throwawaylettersonly"
mkdir -p "$D2R_BACKUP_DIR/$probe"

for ext in d2s ctl key map ma0; do
  if [ -f "$D2R_LIVE_SAVES/$probe.$ext" ]; then
    cp -p "$D2R_LIVE_SAVES/$probe.$ext" "$D2R_BACKUP_DIR/$probe/$probe.$ext"
  fi
done

cp -p "$D2R_STAGE/$probe.d2s" "$D2R_LIVE_SAVES/$probe.d2s"

for ext in ctl key map ma0; do
  if [ -f "$D2R_LIVE_SAVES/$template.$ext" ]; then
    cp -p "$D2R_LIVE_SAVES/$template.$ext" "$D2R_LIVE_SAVES/$probe.$ext"
  fi
done
```

After promotion, confirm the embedded character name and file basename are
letter-only. If the probe is still invisible, compare its status byte at `0x14`
with a fresh in-game throwaway character before assuming the payload was
rejected.

### Warlock Follower Regression

Run after changes to follower payload copying, character creation, scanner
follower checks, or Warlock data regeneration.

```bash
export D2R_SAVES="$D2R_STAGE"

python3 -m d2r_chargen build probewlzero --force
python3 -m d2r_chargen scan probewlzero

D2R_FIXTURES="$D2R_FIXTURES" python3 -m d2r_chargen build probewldemon --force
python3 -m d2r_chargen scan probewldemon
```

Promote one probe at a time with the complete save-family promotion recipe, or
build directly to `D2R_LIVE_SAVES` after backing up any existing live family.

Live observation:

- `probewlzero` appears, enters game, and remains follower-free.
- `probewldemon` appears, enters game, and preserves the bound demon.

Post-run scan:

```bash
python3 tools/d2s_corpus_scan.py \
  "$D2R_LIVE_SAVES/probewlzero.d2s" \
  "$D2R_LIVE_SAVES/probewldemon.d2s" \
  --examples 2
```

### Cross-Class Borrowed Follower Regression

Run after changes to `tools/d2s_forge_follower.py`, scanner follower-tail logic,
or follower stripping assumptions.

```bash
export D2R_SAVES="$D2R_STAGE"

python3 -m d2r_chargen build probesorc --force
python3 -m d2r_chargen scan probesorc

python3 tools/d2s_forge_follower.py \
  "$D2R_STAGE/probesorc.d2s" \
  "$D2R_STAGE/probesorc.borrowed-follower.d2s" \
  --template-d2s "$D2R_DEMON_FIXTURE"

python3 tools/d2s_corpus_scan.py \
  "$D2R_STAGE/probesorc.borrowed-follower.d2s" \
  --examples 2
```

Back up the live `probesorc` family, promote the forged `.d2s`, keep companion
files from a known D2R-created Offline character, and run only this one live
probe.

Live observation:

- The Sorceress enters game.
- The borrowed follower is absent or ignored.
- Save-and-quit rewrites the file without crashing or blocking join.

Post-run scan:

```bash
python3 tools/d2s_corpus_scan.py "$D2R_LIVE_SAVES/probesorc.d2s" --examples 2
```

Restore the backed-up `probesorc` family after the regression check.

### Iron Golem Parser Regression

Run after changes to `kf`/`lf` parsing, Iron Golem payload reporting, or
Necromancer probe generation.

```bash
export D2R_SAVES="$D2R_STAGE"

python3 -m d2r_chargen build probenecro --force
python3 -m d2r_chargen scan probenecro
```

Promote `probenecro`, enter game, create one Iron Golem from a simple known
item, save and quit, then fully exit D2R.

Copy the resulting `.d2s` to a private fixture area outside the public repo and
scan that private copy:

```bash
export D2R_PRIVATE_CAPTURE="/path/to/private/capture/probenecro.golem.d2s"
cp -p "$D2R_LIVE_SAVES/probenecro.d2s" "$D2R_PRIVATE_CAPTURE"
python3 tools/d2s_corpus_scan.py "$D2R_PRIVATE_CAPTURE" --examples 1
```

Record only public-safe aggregate results such as `has_golem_byte`,
`kf_to_lf_gap`, payload length, and payload hash.

### Invalid Follower Safety Check

This is a true future live question, not a routine regression. Run it only if a
scanner-blocking invalid follower case needs live corroboration.

```bash
python3 tools/d2s_forge_follower.py \
  "$D2R_STAGE/probesorc.d2s" \
  "$D2R_STAGE/probesorc.invalid-follower.d2s" \
  --invalid-count-without-payload

python3 tools/d2s_corpus_scan.py \
  "$D2R_STAGE/probesorc.invalid-follower.d2s" \
  --examples 2
```

Expected scanner result: `follower_payload_ok: false`. Scanner hard errors block
deployment unless there is bit-level proof that the scanner is wrong. If this is
promoted for a live negative test, back up first, expect failed join or rewrite,
and restore the backup immediately.

## Completed Public-Safe Results

- A same-install lowercase clone of an in-game throwaway character appeared and
  joined successfully, so cloned saves are not inherently ignored by D2R Offline.
- Companion files matter for character-select visibility. Manual promotion
  should copy a complete save family, not only the `.d2s`.
- Letter-only probe names appeared in D2R's Offline list. Digit-bearing probe
  names such as the old `D2SProbe...` pattern were scanner-clean but invisible on
  the tested install.
- Single-field clone checks did not identify class, level, progression, current
  difficulty, or merc header bytes as the visibility blocker.
- `probewldemon` entered game, the bound demon was present, and after
  save-and-quit the rewritten file stayed scanner-clean with `follower_count=1`
  and 116 trailing payload bytes.
- Borrowed-follower `probesorc` entered game, no follower appeared, and D2R
  stripped the follower block on save-and-quit back to `follower_count=0` with no
  trailing payload.
- `probenecro` with a live-created Iron Golem produced a save with
  `has_golem_byte=1`, `kf_to_lf_gap=58`, and 55 bytes of golem item payload
  before `lf`.
- Reloading that first Iron Golem preserved the same 55-byte payload hash across
  repeated save-and-quit cycles.
- Recasting Iron Golem from a different item rewrote the section as
  `kf_to_lf_gap=29` with a 26-byte payload, confirming that payload length
  follows the encoded item.
- Reloading the second golem preserved the 26-byte length but canonicalized
  payload byte `+1` from `0x20` to `0x00`; a later reload preserved that
  canonicalized payload byte-for-byte.

## Remaining Live Questions

- Confirm the invalid follower mismatch behavior only if scanner results need a
  live negative control.
- Add public-safe aggregate captures for more Iron Golem item categories when
  parser support expands.
- Re-run the visibility, Warlock follower, Sorceress stripping, and Iron Golem
  regression recipes after D2R patches or public save-writer changes.
