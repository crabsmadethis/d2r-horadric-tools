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

- Capture the same bound demon after save/load and after a rebind to a known
  monster. Diff only the 116-byte payload. A damage/heal capture is lower
  priority because bound demons are difficult to keep injured and heal quickly;
  only use it if a durable injured snapshot is easy to create.
- 2026-05-08 live result: `probewldemon` entered game with the copied bound
  demon visible. After save-and-quit, D2R rewrote the save to 1319 bytes while
  preserving `follower_count=1` and exactly 116 trailing payload bytes.
- 2026-05-08 no-combat reload result: `probewldemon` loaded, joined game, and
  save-and-exit preserved the full follower block. Only payload bytes `+89..+91`
  changed (`ea 10 72 -> 8c ee 7b`); identity fields, bitfields, and the
  post-`gf` tail stayed byte-for-byte stable.
- 2026-05-08 live result: two count-2 variants both failed to join game even
  though local scans were size/checksum clean and had exactly 232 trailing
  payload bytes:
  - `probewltwo` copied the same valid 116-byte payload twice.
  - `probewlmix` used two different known 116-byte payloads.
  Neither failed join rewrote the save, so treat live D2R as accepting at most
  one bound demon.
- 2026-05-08 live result: `probewlalt` used `follower_count=1` with the
  alternate known 116-byte demon payload (`tests/fixtures/demon_block_a.bin`).
  The save appeared, joined game, and spawned a demon. After save-and-quit, D2R
  preserved the 116-byte follower block shape but rewrote six payload bytes:
  `+89..+91` and `+95..+97`. Keep treating `+88` and `+95..+115` as runtime or
  hash-like fields for now.
- 2026-05-08 reload result: `probewlalt` still had the demon on reload. A
  second save-and-quit kept `follower_count=1` and 116 trailing payload bytes.
  Payload bytes `+95..+97` stayed stable after the first rewrite, but
  `+89..+91` changed again, so treat `+89..+91` as volatile runtime/hash bytes.
- 2026-05-08 third reload result: `probewlalt` still joined with the demon.
  A third save-and-quit kept the same valid block shape. Bytes `+95..+97`
  remained stable, while `+89..+91` changed to `00 00 00`.
- 2026-05-08 no-combat reload result: `probewlalt` loaded with the demon again.
  After save-and-exit, the payload stayed valid and only bytes `+89..+91`
  changed (`00 00 00 -> ff 8b 58`). The zero triplet is not sticky; keep
  treating `+89..+91` as volatile session/runtime bytes.

### 2. Embedded `gf` inside demon payload

Current assumption: `payload[92:94] == b"gf"` is data, not a structural marker.

Independent next step:

- Count every follower payload in the corpus and verify where `b"gf"` appears.

Live next step:

- Confirm a bound-demon save with a payload still has no extra section after the
  116 bytes by entering game and forcing D2R to rewrite/cache the save.
- 2026-05-08 live result: D2R's rewritten `probewldemon.d2s` ended immediately
  after the 116-byte follower payload; the embedded `gf` was still at payload
  offset 92 and did not behave as a structural marker.

### 3. Cross-class follower behavior

Known: D2R accepted a Sorceress save with a Warlock-style follower payload and
allowed it to enter the world, but did not instantiate the demon.

Independent next step:

- Use `tools/d2s_forge_follower.py` to create a Sorceress staging save with a
  copied demon payload and scanner-check it.

Live next step:

- Load the Sorceress, inspect whether the follower appears, use a waypoint,
  fight one pack, save and quit, then rescan the rewritten save.
- 2026-05-08 live result: borrowed-follower `probesorc` entered game with no
  visible follower. On save-and-quit, D2R rewrote `probesorc.d2s` from the
  promoted `follower_count=1` / 116-byte payload variant back to
  `follower_count=0` with no trailing payload.

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

The initial scanned corpus had `has_golem=0` for every save, so no local fixture
answered the `kf 01 <item>` layout.

Live next step:

- Build/load a Necromancer, create an Iron Golem from a simple item, save and
  quit, then rescan. Keep the captured `.d2s` private unless sanitized.
- 2026-05-08 live result: after creating an Iron Golem on `probenecro`, D2R
  rewrote the save with `has_golem_byte=1`, `kf_to_lf_gap=58`, and 55 bytes of
  golem item payload between `kf 01` and `lf`. The follower block remained
  `follower_count=0`.
- 2026-05-08 persistence result: after fully reloading `probenecro`, the Iron
  Golem was still present in-game. Save-and-quit preserved the same 55-byte
  golem payload (`sha1=2f582d487d12a70b8c5cdc1da3e371b2c302c390`).
- Second reload on 2026-05-08 still showed the Iron Golem in-game and left the
  on-disk save unchanged with the same payload hash.
- Recasting Iron Golem from a different item on 2026-05-08 rewrote
  `probenecro` with `kf_to_lf_gap=29` and a 26-byte golem item payload
  (`sha1=2b0cddc4fb4d6f53db12fa589571c864e8e40e61`). The golem section length
  is item-encoding-dependent, not fixed.
- Reloading that second golem preserved the 26-byte length but changed only
  payload byte `+1` from `0x20` to `0x00` (`sha1` became
  `26515dcb0696db2cd9e60b020fdd3b5c4aa13fb1`), making `+1` a runtime/state
  candidate rather than item identity.
- A subsequent reload/save preserved that canonicalized 26-byte payload
  byte-for-byte, so the `+1` change appears to be a one-time normalization.
- 2026-05-08 preserve-path result: `probegolem`, a disposable `probenecro`
  clone rebuilt through `rebuild_items(...)`, appeared in D2R, joined game, and
  still had the Iron Golem. After save-and-quit, the golem payload stayed
  byte-for-byte identical (`sha1=5708645b2c93a15e1e6ae45aed48f74a85975a65`),
  with header `type=flc`, `quality=4`, `storage=0`, `location=1`,
  `bodyloc=4`.
- 2026-05-08 generated-writer result: `probegnorm` used a generated
  normal-quality Falchion payload from `build_item(...)`, not a copied live
  golem payload. It joined game. After save-and-quit, D2R kept `has_golem=1`,
  payload length 19, header `type=flc`, `quality=2`, `storage=0`,
  `location=1`, `bodyloc=4`, and preserved the payload byte-for-byte
  (`sha1=4818f07bc1e0e0907f4bcd30a50ab7c6038fb82d`).
- 2026-05-08 generated-magic result: `probegmag` used a generated magic-quality
  Falchion payload with an encoded `fireresist +10` property. It joined game.
  The on-disk save remained `has_golem=1`, payload length 24, header
  `type=flc`, `quality=4`, `storage=0`, `location=1`, `bodyloc=4`, and the
  payload remained byte-for-byte identical
  (`sha1=09e7961cd4d3763fda1a073493aa97c00e38b4fd`). The file timestamp/hash
  did not change, so record this as join acceptance plus valid on-disk
  persistence, but not as a visual-presence probe.
- 2026-05-08 chargen support result: v1 YAML support can now inject one
  generated normal or magic Iron Golem item for Necromancers with
  `skills: {IronGolem: 1}`. It writes the same live-observed storage shape
  (`storage=0`, `location=1`, `bodyloc=4` for the default weapon slot) and
  deliberately rejects sockets, runewords, uniques, sets, rares, and crafted
  items until those encodings get their own live probes.
- 2026-05-08 YAML live result: `probegyaml` was generated through the
  `iron_golem:` YAML path with a magic Falchion carrying `fire_res: 10`.
  It appeared in Offline, joined game, and the Iron Golem was visually present.
  After save-and-exit, D2R still reported `has_golem=1`, payload length 24,
  header `type=flc`, `quality=4`, `storage=0`, `location=1`, `bodyloc=4`, and
  preserved the golem item payload byte-for-byte
  (`sha1=8c5b252152951340325803723c8c166adacef406`).

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
