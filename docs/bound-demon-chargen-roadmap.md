# Bound Demon Chargen Roadmap

This roadmap describes the public chargen path from template cloning toward
more robust Reign of the Warlock bound-demon generation.

## Goal

Safe v1 support copies a known template payload:

```yaml
bound_demon:
  template: known_template
```

The robust target is a YAML surface that can author a demon from stable fields:

```yaml
bound_demon:
  template: known_template
  monster_hcidx: 20
  source_affixes: [Cursed]
  skill_affixes: auto
```

Full synthesis without a template remains blocked until the remaining runtime
and hash-like bytes are decoded or proven ignorable.

## Field Confidence

| Offset | Meaning | Writer confidence |
| --- | --- | --- |
| `+0..+1` | follower kind tag `0x0018` | fixed |
| `+4..+5` | `monster_hcidx` | authorable in template-derived payloads |
| `+6..+9` | monster seed | preserve template value; arbitrary override is unsafe |
| `+52..+55` | persisted bind metadata | persistent; not proven to be current Bind Demon skill level |
| `+80..+86` | seven MonUMod affix bytes | authorable in template-derived payloads; composed from source affixes plus Bind Demon threshold affixes for player-facing YAML |
| `+89..+91` | volatile runtime bytes | do not author |
| `+92..+93` | embedded `gf` payload data | data, not a section marker |

The seven MonUMod bytes do not explain every visible property. Some properties
still require compatible source-affix context such as the observed
`bitfields_64_79` slice, but `+85/+86` are now decoded as overflow affix slots
rather than model-candidate bytes.

Recent live validation tightened two important limits:

- A direct Spectral Hit plus Aura Enchanted affix-byte override persisted in
  the save, but did not visibly display those properties.
- A non-template monster seed caused D2R to save the character back with
  `follower_count=0`, so seed override must stay blocked until seed semantics
  are decoded.
- A natural bind with the Warlock skill block showing Bind Demon level 20 still
  saved payload `+52` as `7`; do not treat this field as the current skill
  level until a natural bind-level matrix explains it.
- Natural binds at hard Bind Demon levels 1, 5, 10, and 20 all saved payload
  `+52` as `7`, while writing the expected threshold affixes into the MonUMod
  bytes. This confirms `+52` is not effective Bind Demon level.
- A pre-authored empty-affix follower matrix at hard Bind Demon levels 1, 5,
  10, 15, and 20 displayed no added properties and saved back with unchanged
  empty affix bytes. Skill level and payload `+52` are therefore not sufficient
  to make tooltip-granted properties appear on an authored follower.
- Original-template and forced-monster payloads displayed authored normal
  affixes when the source context was compatible. Spectral Hit plus
  Aura Enchanted can live in the overflow slots at `+85/+86`. Clearing the
  MonUMod vector removes all visible extra properties.
- A natural over-cap Bind Demon 20 capture saved seven affix slots:
  Cursed, Aura Enchanted, Teleportation, Extra Strong, Extra Fast,
  Spectral Hit, and none. This proves five bytes was a parser limit, not the
  demon affix capacity.

## Support Tiers

| Tier | YAML | Meaning | Status |
| --- | --- | --- | --- |
| 1 | `template: NAME` | Copy a known 116-byte payload | Supported |
| 2 | template plus safe field overrides | Edit proven fields while preserving the rest | Experimental |
| 3 | template plus monster identity changes | Change model while borrowing compatible runtime fields | Experimental |
| 4 | fully synthesized payload | Build all 116 bytes without a template | Blocked |

## YAML Affix Model

Use `source_affixes` for affixes the monster already had before binding, and
use `skill_affixes: auto` for the Bind Demon threshold affixes. Auto skill
affixes derive from the generated character's effective Bind Demon level, using
hard points plus active player equipment and inventory skill bonuses. If the
player binds on weapon swap or another state chargen cannot infer, set
`effective_bind_level` explicitly.

Use `template: NAME` for a tracked fixture/template name. Use
`template_path: PATH` for a local `.d2s` template kept outside tracked public
files. Source-affix visibility can depend on template context bytes such as the
observed `bitfields_64_79` slice, so a source-affix-heavy demon should use a
template captured or proven with compatible source-affix context.
When Fanaticism and Aura Enchanted are both requested through the
player-facing composer, chargen emits them as `Fanaticism, Aura Enchanted`
before the remaining composed affixes. This matches the live-positive
Black Lancer aura path.

Examples:

```yaml
bound_demon:
  template: known_template
  monster_hcidx: 20
  source_affixes: []
  skill_affixes: auto
```

```yaml
bound_demon:
  template: known_template
  monster_hcidx: 20
  source_affixes: [Cursed, Lightning, Cold Enchanted]
  skill_affixes: auto
  effective_bind_level: 10
```

```yaml
bound_demon:
  template_path: .local-demon-templates/black_lancer_fanat.d2s
  monster_hcidx: 724
  source_affixes: [Fanaticism, Aura Enchanted, Cursed, Stone Skin]
  skill_affixes: auto
  effective_bind_level: 20
```

The legacy `affixes` field is still accepted as a raw seven-slot override for
research controls. Do not combine it with `source_affixes` or
`skill_affixes`.

## Remaining Work

- Decode or classify unknown slices at `+24..+31`, `+44/+48`, `+64..+79`,
  `+88`, and `+95..+115`.
- Prove which template/model fields control visible demon shape.
- Add more player-facing templates once model identity and seed compatibility
  are better understood.
- Build canonicalization-aware assertions for any field D2R rewrites on
  save/exit.
- Promote experimental YAML fields only after the scanner and docs agree on the
  field confidence.

## Full Synthesis Proof Ladder

The target for full synthesis is a writer that can build the complete 116-byte
bound-demon payload from stable inputs instead of cloning a live template. A
rare high-tier capture, such as a Matron's Den Black Lancer, is useful final
evidence but is not the cheapest next proof: one rare payload mostly expands
the template library unless the generic byte rules are already understood.

Use this ladder before promoting template-free YAML:

1. **Corpus classification.** Decode every available bound-demon payload and
   classify each byte or slice as fixed, volatile, seed-correlated,
   monster-correlated, affix-correlated, or currently unknown. Public output
   must be aggregate only; do not print local paths or commit raw saves. The
   public helper is `tools/d2s_demon_payload_corpus.py`. Its
   `model_candidate_offsets` section highlights bytes fixed within each
   monster id but different across monster ids, after known seed/hcIdx/affix
   fields are filtered out.
2. **Same-model natural binds.** Bind the same easy monster repeatedly with no
   source affixes and low Bind Demon level. This isolates random seed and
   runtime fields from stable model fields.
3. **Affix-only controls.** Hold monster identity constant and vary source
   affixes and effective Bind Demon thresholds. This confirms which visible
   labels are represented by the seven MonUMod bytes and which labels still
   need source context, monster-specific state, or runtime recomputation.
4. **Slice mutation controls.** Starting from one valid payload, mutate only one
   unknown slice at a time (`+24..+31`, `+44/+48`, `+64..+79`, `+88`,
   `+95..+115`) while preserving seed, model, bind metadata, and affixes. After
   live load/save, classify the result as accepted-preserved,
   accepted-rewritten, accepted-hidden-broken, or stripped. The public helper
   for this lab is `tools/d2s_forge_demon_payload.py`, using `--zero-slice`,
   `--set-slice-hex`, or `--copy-slice-from` for named slices from
   `DEMON_UNKNOWN_SLICE_RANGES`.
   Current Fallen same-model evidence says `+96/+97`, `+104/+105/+106`, and
   `+109/+111/+112` are accepted-rewritten, `+101/+102` can join but save back
   as an invalid 106-byte follower payload, `+115` is load-critical when
   zeroed, and changing `+114` strips the follower on save. Preserve the final
   `f0 1f` bytes for same-model Fallen before model-swap work.
5. **Same-family model swaps.** Reuse a donor payload inside one monster family
   (for example Fallen variants, Lancer variants, or Blunderbore/Mauler/Urdar
   variants) and change only `monster_hcidx`. This tests whether unknown bytes
   are family-generic or model-specific. Current Fallen-family results say
   hcIdx-only swaps are not sufficient: one target was visible but stripped on
   save, and another preserved a hidden non-visible payload. Before promoting
   another generated model swap, compare the candidate rows with:

   ```bash
   python3 tools/d2s_monster_model_compare.py \
     --excel-dir <extracted-excel-dir> \
     --hcidx <donor-row-index> <target-row-index>
   ```

   For Fallen/Carver/Devilkin (`19/20/21`), selected MonStats2 body/animation
   fields were identical aside from row id, while MonStats differed in
   transform level, AI params, speed, levels, combat stats, and elemental
   flavor.
   When a candidate offset set exists, the forge helper can stage one explicit
   hypothesis with exact offset copies:

   ```bash
   python3 tools/d2s_forge_demon_payload.py <source.d2s> <probe.d2s> \
     --monster-hcidx <target-hcidx> \
     --copy-offsets-from '+024,+028:<donor.d2s>' \
     --force-combined-mutations
   ```

   The Council Member and Black Lancer chain is now completed evidence rather
   than an active probe queue. The first Council Member-style exact-offset
   probe was live-positive with visible model generation and post-save
   `follower_count=1`. Post-save canonicalization preserved `+24`, `+28`,
   `+100`, `+103`, `+105`, `+110`, `+111`, and `+112`, while rewriting seed,
   volatile bytes, affix-overflow bytes `+85/+86`, `+95`, and `+97`. A reduced
   preserved-offset probe was also live-positive, and the follow-up hcIdx-only,
   stats-only (`+24/+28`), and tail-only
   (`+100/+103/+105/+110/+111/+112`) reduction probes all worked for Council
   Member `347`. That target can therefore be generated from the current Fallen
   control with hcIdx-only model editing.

   Payload `monster_hcidx` values must be looked up as zero-based MonStats row
   indexes, not through the MonStats `*hcIdx` column; a value `723` probe loaded
   as DarkArcher because row index `723` is `cr_archer8`. Correcting the row
   value to `724` (`cr_lancer9`) was live-positive: the save joined as
   Black Lancer and saved back with `follower_count=1`, a 116-byte payload, and
   `monster_hcidx=724`.

   Black Lancer affix work is also completed evidence. A direct level-1
   generated-shell affix package loaded with no visible affixes and saved back
   with those affix bytes zeroed. A natural hard Bind Demon 20 shell preserved
   real skill-granted affixes after changing only the model to Black Lancer,
   displaying Extra Strong, Extra Fast, Spectral Hit, and Aura Enchanted. A
   creative Fanaticism/Cursed/Stone Skin tuple then proved byte persistence is
   not enough by itself: the desired bytes saved back, but those source-style
   labels were not visibly active. Copying natural source-affix context from a
   hard-level 10 bind showed `bitfields_64_79` is sufficient to activate Cursed
   and Stone Skin on Black Lancer, while the copied post-`gf` tail did not
   change the visible result.
   The follow-up aura-context batch showed that Aura Enchanted alone did not
   expose a visible aura label in the tested Black Lancer source context.
   Fanaticism plus Aura Enchanted did expose Aura Enchanted with Fanaticism,
   while preserving Stone Skin, Extra Strong, and Extra Fast. A champion-style
   bitfield borrowed from a Ghostly capture did not change the bound demon
   nameplate color. This makes Fanaticism a separate source/aura-flavor input
   that pairs with Aura Enchanted; it is not part of the Bind Demon threshold
   table. The final tradeoff batch was also live-positive and preserved its
   affix bytes after save/exit: one package kept Fanaticism, Aura Enchanted,
   Cursed, Stone Skin, and Extra Strong; another swapped Extra Strong for
   Extra Fast; and another dropped Stone Skin to keep both Extra Strong and
   Extra Fast. All three are valid Black Lancer packages; the practical choice
   is a build-design tradeoff rather than a save-format blocker.
   A generated seven-slot Black Lancer package then displayed all intended
   labels, including Spectral Hit, with an active Fanaticism aura and saved
   back with the follower payload unchanged.
6. **Cross-family model swaps.** Repeat the `monster_hcidx` swap across
   unrelated AI/model families. Failures here are expected and useful because
   they identify which fields must come from MonStats/MonStats2 or runtime
   construction instead of a generic initializer.
7. **Synthetic initializer.** Build a payload from constants plus generated
   fields, with no template payload bytes. It must scan clean, load visibly,
   survive save/exit with `follower_count=1`, and preserve the intended model
   and visible affixes after D2R canonicalization.
8. **High-tier validation.** Only after the cheaper controls pass, validate the
   same writer against expensive targets such as a Matron's Den Black Lancer or
   other Pandemonium/Terror Zone demons.

Acceptance for template-free support requires more than "scanner-clean": D2R
must instantiate the demon, keep it after save/exit, and either preserve or
predictably canonicalize every authored field.

## Public Validation Standard

Use `docs/manual-save-validation.md` for any local game validation. Public docs
should record the stable behavior and limitation, not disposable character
names, machine details, or session logs.

## Completed Manual Probe Evidence

Bind Demon table review confirmed that the real skill adds monster affix ids at
specific skill thresholds during the bind action:

| Bind Demon level | Expected skill-granted affixes |
| --- | --- |
| `1..4` | none |
| `5..9` | Extra Strong |
| `10..14` | Extra Strong, Extra Fast |
| `15..19` | Extra Strong, Extra Fast, Spectral Hit |
| `20+` | Extra Strong, Extra Fast, Spectral Hit, Aura Enchanted |

The natural-bind matrix is complete. The validation characters started with no
follower and bound fresh demons in game so D2R ran the actual Bind Demon server
function at hard skill levels 1, 5, 10, 15, and 20.

Those controls intentionally avoided Annihilus, Hellfire Torch, skillers,
`all_skills`, and `class_skills`. They instead used rare non-skill gear and
small charms for durability, resists, cast/recovery speed, damage reduction,
open wounds, crushing blow, prevent heal, and slow target. This kept the hard
Bind Demon thresholds exact while still making the manual bind attempts
practical.

Natural-bind results:

| Hard level | Source | Visible result | Payload affixes |
| ---: | --- | --- | --- |
| 1 | Hell Fallen | no added properties | none |
| 5 | Hell Fallen | Extra Strong | `5` |
| 10 | rare Hell Fallen, started Lightning/Cold/Cursed | retained source affixes, gained Extra Strong and Extra Fast | `7, 17, 18, 5, 6` |
| 15 | Hell Fallen | Extra Strong, Extra Fast, Spectral Hit | `5, 6, 27` |
| 20 | Hell Fallen | Extra Strong, Extra Fast, Spectral Hit, Aura Enchanted | `5, 6, 27, 30` |

The natural-bind matrix confirms that D2R writes the expected threshold affixes
into the MonUMod bytes during the bind action. Existing source-monster affixes
can carry through ahead of or alongside those threshold affixes. Chargen now
models these as two inputs: `source_affixes` and derived `skill_affixes`.

The same-model seed-control batch used five level-1, no-+skill controls. The
goal was to bind the same easy white demon type on each character, fully exit
D2R, scan the saves, then run:

```bash
python3 tools/d2s_demon_payload_corpus.py <seed-control-save-paths>
```

Current same-model seed-control results:

| Control group | Result |
| --- | --- |
| Three clean controls | `monster_hcidx=20`, `bind_metadata=7`, affix tuple `0000000000` |
| Source-affix control | `monster_hcidx=20`, `bind_metadata=7`, affixes Spectral Hit, Stone Skin, Extra Strong |
| Source-affix control | `monster_hcidx=20`, `bind_metadata=7`, affixes `resist`, Mana Burn, Teleportation |

Across the three clean controls, only 9 of 116 payload bytes varied. The
variable regions were the monster seed bytes, two bytes inside
`bitfields_64_79`, one volatile byte at `+89`, and four bytes inside
`post_gf_tail_95_115`. The unknown slices `runtime_stats_24_31`,
`percent_or_caps_44_51`, `hash_or_runtime_byte_88`, and `post_gf_opcode_94`
were fixed for the clean controls.

The two source-affix captures are still useful, but they should not be mixed
with the clean seed controls when classifying seed-only variation.

The one-slice mutation batch used the clean seed controls as its baseline. It
changed only one unknown slice per probe while preserving monster identity,
seed, bind metadata, and affix bytes. The first live classification targets
were:

| Slice target | Mutation |
| --- | --- |
| `volatile_runtime_89_91` | zero the three volatile bytes |
| `bitfields_64_79` | copy the clean-control donor variant |
| `post_gf_tail_95_115` | copy the clean-control donor variant |

Those first one-slice results were positive for same-model Fallen controls: all
three accepted, stayed plain bound Fallen, and saved back with one 116-byte
payload. D2R rewrote the volatile slice, preserved the donor bitfield variant,
and partially canonicalized the post-`gf` tail by rewriting `+96/+97` while
preserving donor `+101/+102`.

The fixed-slice controls tested whether `runtime_stats_24_31`,
`percent_or_caps_44_51`, `hash_or_runtime_byte_88`, and `post_gf_opcode_94`
were ignored, rewritten, or required. They also stayed visually normal as bound
Fallen.
D2R rewrote `runtime_stats_24_31` and `hash_or_runtime_byte_88`, preserved a
nonzero `percent_or_caps_44_51` pattern, and exposed `post_gf_opcode_94` as a
structural byte: changing it from `06` to `00` joined once but saved back as a
scanner-invalid variable-length follower block. Keep `+94` at `06` for known
116-byte bound-demon payloads.

The zero-bitfield probe was accepted and saved back cleanly. The all-zero
post-`gf` tail probe froze/failed to join, so the tail is load-critical and
had to be split. The later tail probes showed `+96/+97`,
`+104/+105/+106`, and `+109/+111/+112` are accepted-rewritten,
`+101/+102` can produce an invalid 106-byte follower payload, `+115` is
load-critical when zeroed, and changing `+114` strips the follower on save.

For practical higher-level binding, keep high-survival binder templates as local
validation inputs outside the tracked `chars/` folder. These are not
threshold-exact controls when they intentionally use player +skill gear.

The secondary manual batch is the synthetic combo control. Keep those generated
character drafts local and use them only after the natural-bind matrix if the
affix labels still need byte-combination isolation.
