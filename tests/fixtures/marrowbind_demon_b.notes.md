# marrowbind_demon_b.d2s — Fixture metadata

**Captured:** 2026-04-25 ~23:18 (mtime of source file)

**Character:** Marrowbind, Warlock, level 99, hardcore, hell

**Bound demon:** Fallen (per user — "I bound a fallen"). Decoded `monster_hcidx` at +4 = 20 = `fallen2` per `vanilla/data/global/excel/MonStats.txt` row 22.

**Bind Demon skill level:** 7 (decoded at +52 of demon block)

**Affix indices (decoded at +80..+84):** `19 06 05 1b 1e` = 25 (?), 6 (Extra Fast), 5 (Extra Strong), 27 (Spectral Hit), 30 (Aura Enchanted)

**Notes:**

- This save replaced the previous Marrowbind state where a different monster had been bound. The original demon block bytes (Fixture A) were captured from session memory before the rebind and stored at `demon_block_a.bin`. The full pre-rebind .d2s file is gone (D2R rotates `.maN` files but not `.d2s` snapshots).
- This fixture is the canonical "warlock with active bound demon" test artifact. Used by:
  - `tests/test_follower_block.py` — decoder tests
  - `tests/test_follower_block_scanner.py` — scanner integration
  - `tests/test_follower_block_round_trip.py` — write-path tests
  - `chars/Marrowbind.yaml` (Phase 3.4) — `bound_demon: {template: marrowbind_demon_b}` reference
