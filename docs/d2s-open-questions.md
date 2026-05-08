# D2S Open Questions Plan

Status: working plan for `codex/d2s-open-questions`.

This file tracks `.d2s` questions that can be answered from public code,
private local fixtures, and controlled live-game smoke tests. It is deliberately
split into independent work and live-test work so public-safe commits can move
forward without waiting on a game session.

## Independent Work

### Corpus aggregation

Use `tools/d2s_corpus_scan.py` to scan local `.d2s` files without printing full
paths or character names.

Recommended Bazzite command:

```bash
python3 tools/d2s_corpus_scan.py \
  ~/recovered-repos/d2r-horadric-tools \
  ~/SK256-extracted/steamdeck-backup/deck \
  --examples 5
```

The first read-only pass on Bazzite found:

| Finding | Result |
| --- | --- |
| Valid `.d2s` files | 1757 |
| File version | all `105` |
| Size header | all matched `len(data)` |
| Checksum | all matched rotate-left checksum |
| `kf` to `lf` gap | always 5 bytes |
| `has_golem` byte | always `0` in the scanned corpus |
| `follower_count=0` | 1653 saves |
| `follower_count=1` | 104 saves |
| `follower_count=1` with 116 payload bytes | 102 saves |
| `follower_count=1` with 0 payload bytes | 2 saves, useful as negative fixtures |
| `jf` present before merc `JM` | 879 saves |
| `jf` absent before merc `JM` | 878 saves |

The aggregate pass supports the current follower-block invariant:

```text
follower_count == N => exactly N * 116 payload bytes follow lf<u16>
```

### Public docs drift

`docs/d2s_format.md` already has the newer follower-block model. The older
`docs/save-format.md` still uses `lf_count` wording in places and describes
`lf` as if it is always the final bytes. That document should either be retired
in favor of `docs/d2s_format.md` or updated to call the field
`follower_count` and mention optional 116-byte follower payloads after `lf`.

### Utility coverage

`tools/d2s_forge_follower.py` provides a staged way to create these variants:

- copy a 116-byte follower payload from a template `.d2s`
- copy a raw `demon_block_*.bin` payload
- strip the follower block to `follower_count=0`
- intentionally create the negative `follower_count=1` plus no payload case

It writes only to an explicit output file and recomputes file size/checksum.
Use the scanner before copying any forged output into live saves.

## Open Questions

### 1. Demon payload runtime fields

Unknown fields:

- `+24..+31`: likely monster-derived runtime stats
- `+64..+79`: bitfields that differ between known binds
- `+88`: high-entropy `u32`, possibly a hash or runtime state
- `+95..+115`: variable payload after embedded `gf`

Independent next step:

- Extend the corpus scanner or a small fixture decoder to aggregate those
  offsets across every 116-byte follower payload already present locally.

Live next step:

- Capture the same bound demon after damage/heal, after save/load, and after a
  rebind to a known monster. Diff only the 116-byte payload.

### 2. Embedded `gf` inside demon payload

Current assumption: `payload[92:94] == b"gf"` is data, not a structural marker.

Independent next step:

- Count every follower payload in the corpus and verify where `b"gf"` appears.

Live next step:

- Confirm a bound-demon save with a payload still has no extra section after the
  116 bytes by entering game and forcing D2R to rewrite/cache the save.

### 3. Cross-class follower behavior

Known: D2R accepted a Sorceress save with a Warlock-style follower payload and
allowed it to enter the world.

Unknown: whether the demon spawns, is ignored, or becomes unstable during play.

Independent next step:

- Use `tools/d2s_forge_follower.py` to create a Sorceress staging save with a
  copied demon payload and scanner-check it.

Live next step:

- Load the Sorceress, inspect whether the follower appears, use a waypoint,
  fight one pack, save and quit, then rescan the rewritten save.

### 4. Merc status at `0xA7..0xA8`

Existing docs said observed values were `{0, 1, 9, 15}`. The Bazzite corpus
shows additional values such as `3`, `11`, `50`, `16`, `18`, `5`, and `21`.

Independent next step:

- Group `merc_status_u16_0xA7` by hireling id, merc item count, class id,
  progression, and difficulty bytes.

Live next step:

- Capture before hiring, after hiring, after merc death, after resurrecting,
  after changing difficulty, and after removing merc gear.

### 5. Iron golem block

The scanned corpus has `has_golem=0` for every save, so no local fixture answers
the `kf 01 <item>` layout.

Live next step:

- Build/load a Necromancer, create an Iron Golem from a simple item, save and
  quit, then rescan. Keep the captured `.d2s` private unless sanitized.

### 6. `jf` marker optionality

Current docs imply `jf` is always present between the corpse `JM` and merc `JM`.
The corpus is split almost exactly in half: 879 saves have a `jf` before the merc
`JM`, and 878 do not, while both groups still have the `JM[merc] | kf | lf` tail.

Independent next step:

- Group `has_jf_before_merc_jm` by file age/source, writer generation, class id,
  merc item count, and follower count.

Live next step:

- Build a new probe save with current chargen, enter game, save and quit, and
  check whether D2R preserves or removes the `jf` marker.

## Safety Rules

- Fully exit D2R before copying `.d2s` files.
- Back up every live `.d2s` before overwriting.
- Back up companion files (`.ctl`, `.key`, `.map`, `.ma0`) before overwriting
  them during character-select visibility tests.
- Write forged variants to `/tmp` or another staging directory first.
- Run `python3 tools/d2s_corpus_scan.py <file>` and `d2r-chargen scan <name>`
  before promoting a staged save.
- A scanner-clean `.d2s` can still be invisible in character select if its
  companion files or SC/HC display category do not match the active profile.
- On the 2026-05-08 Bazzite session, adding copied companions plus matching
  `0x14 == 0x04` still did not make digit-bearing `D2SProbe...` characters
  visible. Same-install letter-only clones did appear, including clones that
  changed class, level, progression, current difficulty, and merc header bytes.
  The letter-only aliases `probesorc`, `probenecro`, `probewlzero`, and
  `probewldemon` all appeared in the Offline list. Use letter-only probe names
  before concluding the probe payload is bad.
- Only copy one test character at a time into the live save directory.
- After each live result, copy the rewritten save back to a private fixture area
  and record only aggregate findings in public docs.
