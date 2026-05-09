# D2S Open Questions Plan

Status: public-safe findings and remaining questions after the 2026-05-08 live
probe cleanup.

This file tracks `.d2s` questions that can be answered from public code,
private local fixtures, and controlled live-game smoke tests. It is deliberately
split into independent work and live-test work so public-safe commits can move
forward without waiting on a game session.

## Independent Work

### Corpus aggregation

Use `tools/d2s_corpus_scan.py` to scan local `.d2s` files without printing full
paths or character names.

Recommended command with sanitized corpus roots:

```bash
D2S_CORPUS_ROOT_A=/path/to/public-or-private-corpus-a
D2S_CORPUS_ROOT_B=/path/to/public-or-private-corpus-b
python3 tools/d2s_corpus_scan.py \
  "$D2S_CORPUS_ROOT_A" \
  "$D2S_CORPUS_ROOT_B" \
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

## Question Status

### 0. Live probe visibility gate

Status: answered for this install.

Answered finding:

- Scanner-clean, same-install clones were not automatically visible when their
  embedded names and basenames contained digits. Letter-only aliases appeared
  and loaded, while the digit-bearing `D2SProbe...` family stayed invisible.

Next proof method:

- Treat letter-only names as the default for every live `.d2s` probe. Only use
  digit-bearing names in an explicit negative-control test.

### 1. Demon payload runtime fields

Status: still open, with several subquestions answered.

Answered findings:

- A Warlock bound demon with `follower_count=1` and one 116-byte payload is
  accepted, visible, and preserved across no-combat reload/save cycles.
- Two separate `follower_count=2` probes were scanner-clean but failed to join
  game, so live D2R should be treated as accepting at most one bound demon.
- The repeated volatile slice is `+89..+91`; it can change to or from
  `00 00 00`, so writers should not author it.
- The five MonUMod bytes at `+80..+84` are authorable and control visible extra
  affixes, but they do not exhaust every visible property.
- `monster_hcidx` is authorable enough to change the visible demon model in the
  tested template-derived path.
- Bind Demon level at `+52` persists, but the first level-only test did not
  prove visible behavior.
- The second edited-payload batch preserved all authored affix bytes. Cold
  Enchanted and Stone Skin showed visibly; Lightning Enchanted byte `03`
  persisted but did not display as Lightning Enchanted for this bound demon.
- Experimental template-derived `bound_demon:` YAML overrides now support
  `monster_hcidx`, `monster_seed`, `bind_level` / `bind_demon_level`, and up to
  five `affixes` padded with zeros.
- The first YAML-generated override probe (`demexp`) appeared in Offline,
  joined game, and showed the requested Fallen model with Extra Strong plus
  Extra Fast affixes. After save-and-exit, D2R preserved the authored
  `monster_hcidx`, seed, bind level, and affix bytes; only known volatile bytes
  `+89..+91` changed.

Still open:

- `+24..+31`, `+44/+48`, `+64..+79`, `+88`, and `+95..+115` remain runtime,
  hash, derived-stat, or RotW-tail candidates.
- The `bindtank` capture kept Aura Enchanted, Spectral Hit, and lightning
  immunity visible even though they were absent from the five decoded MonUMod
  bytes. Those properties are stored elsewhere, implicit from the monster, or
  omitted from the persisted MonUMod list.
- Fully synthesized 116-byte demon payloads remain blocked until the unknown
  slices are decoded or proven ignorable by live reload/save evidence.

Next proof methods:

- Extend the corpus scanner or a small fixture decoder to aggregate the unknown
  offsets across every local 116-byte follower payload.
- Continue natural high-property captures and template-derived single-affix
  probes. Diff only the 116-byte payload and separate stable identity fields
  from volatile/runtime bytes.
- Run a Bind Demon level matrix only after the identity and affix fields have a
  stable baseline.

### 2. Embedded `gf` inside demon payload

Status: answered.

Answered finding:

- The embedded `payload[92:94] == b"gf"` is payload data, not a structural
  marker. A rewritten bound-demon save ended immediately after the 116-byte
  follower payload.

Next proof method:

- Keep corpus-level counting of `b"gf"` positions as a cheap regression check,
  but do not block writers on this question.

### 3. Cross-class follower behavior

Status: answered for the Sorceress borrowed-follower probe; broader class
matrix still open.

Answered finding:

- A Sorceress save with a structurally valid Warlock follower payload entered
  the world, but no demon appeared. On save-and-quit, D2R stripped the save back
  to `follower_count=0` with no trailing payload.

Next proof method:

- Keep cross-class follower payloads out of normal chargen. If other classes
  matter, test one disposable letter-only class probe at a time and rescan after
  save-and-quit.

### 4. Merc status at `0xA7..0xA8`

Status: still open.

Known evidence:

- Existing docs listed `{0, 1, 9, 15}`. The aggregate corpus also shows values
  such as `3`, `5`, `11`, `16`, `18`, `21`, and `50`.

Next proof methods:

- Group `merc_status_u16_0xA7` by hireling id, merc item count, class id,
  progression, and difficulty bytes.
- Run a disposable live ladder: before hiring, after hiring, after merc death,
  after resurrecting, after changing difficulty, and after removing merc gear.

### 5. Iron Golem block

Status: answered for layout, single-golem behavior, preservation, and v1
normal/magic YAML support; still open for full item-family visual coverage.

Answered findings:

- The Iron Golem lives in the `kf` section before `lf` as one variable-length
  item payload. The section is item-encoding-dependent, not fixed length.
- Two live captures had different payload lengths (`kf_to_lf_gap=58` with a
  55-byte payload, and `kf_to_lf_gap=29` with a 26-byte payload).
- Recasting replaced the existing golem rather than appending another payload.
- One 26-byte payload canonicalized byte `+1` from `0x20` to `0x00` on first
  reload/save, then stabilized.
- Rebuild preservation kept an existing golem payload byte-for-byte in the
  tested path.
- Generated normal and magic Iron Golem payloads are supported through the v1
  YAML path for Necromancers with `IronGolem` learned. The normal/magic YAML
  support has visual positive evidence and checksum-clean post-save evidence.
- Broader generated families appeared in Offline, joined game, and saved back
  with `has_golem=1`, valid golem headers, checksum OK, and
  `follower_count=0`. Empty socketed normal, set, and ethereal crafted payloads
  preserved byte-for-byte; Steel runeword and unique Bloodrise payloads stayed
  active but canonicalized payload bytes.

Still open:

- The expansion-family batch was not fully visually confirmed, so record it as
  load/save persistence until a visual pass covers each family.
- Runeword and unique golems need canonicalization-aware assertions rather than
  strict byte-preservation expectations.

Next proof methods:

- Add a visual confirmation matrix for the expansion-family batch, one
  letter-only probe at a time.
- Keep v1 normal/magic writer support separate from experimental socketed,
  runeword, unique, set, rare, and crafted promotion decisions.

### 6. `jf` marker optionality

Status: still open.

Known evidence:

- The corpus is split almost exactly in half: 879 saves have `jf` before the
  merc `JM`, and 878 do not, while both groups still have the
  `JM[merc] | kf | lf` tail.

Next proof methods:

- Group `has_jf_before_merc_jm` by file age/source, writer generation, class id,
  merc item count, and follower count.
- Build a new probe save with current chargen, enter game, save and quit, then
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
