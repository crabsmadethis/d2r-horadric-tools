# Phase 0.4 — `follower_count=1` Acceptance Test Results

**Tested:** 2026-04-25 by user, in-game on this Steam Deck install.

**Hypothesis:** D2R rejects `follower_count=1` only when the 116-byte follower payload is missing. The 2026-04-20 author's "always write 0" fix overshot — they only needed count and payload to stay in sync.

## Method

`scripts/dev/forge_lf_test.py` derived two saves from `tests/fixtures/tempest.d2s` (Sorceress, lvl 99, HC):

| Save     | Char name | follower_count | Payload | Size  | Expected |
|----------|-----------|----------------|---------|-------|----------|
| LfTestA  | LfTestA   | 1              | none    | 2201B | REJECT   |
| LfTestB  | LfTestB   | 1              | 116B from Marrowbind (fallen demon) | 2317B | ACCEPT |

Both deployed to the live D2R saves dir. User fully relaunched D2R and attempted to enter game with each character.

## Result

| Save     | Outcome                  |
|----------|--------------------------|
| LfTestA  | "FAILED TO JOIN GAME" — kicked back to char select. D2R never wrote any cache files (no `.ma0` / `.ma1` / `.ctl`). |
| LfTestB  | **Loaded into game successfully.** D2R wrote a full set of cache files (`.ma0`, `.map`, `.ctl`, `.key`). |

## Conclusion

✅ **Hypothesis confirmed.** The acceptance rule is exactly:

```
follower_count == N  ⇒  exactly N follower payloads must follow
```

For `N == 1` (the only currently-supported case), this means exactly 116 bytes of demon-block payload after the `lf<u16>` marker.

### Implications for the writer (Phase 3)

1. When chargen builds a Warlock **without** `bound_demon:` YAML → write `follower_count = 0`, no payload. (Status quo.)
2. When chargen builds a Warlock **with** `bound_demon: {template: ...}` → write `follower_count = 1` AND the full 116-byte payload from the template fixture.
3. Round-trip-preserve mode → copy the existing follower block bytes verbatim (count + payload together).
4. **Never write `follower_count >= 1` without the payload.** D2R rejection is silent and immediate ("FAILED TO JOIN GAME").

### Surprising side observation

Variant B was a **Sorceress** save with a Warlock-style bound-demon payload, and D2R accepted it. So D2R does NOT class-gate the follower block at load time — it accepts any class with a follower block present.

**Open question (out of scope for v1):** what does D2R *do* with the demon block when the character is a non-warlock? Does it silently ignore it? Spawn a demon anyway? Crash on first interaction? We didn't actually play LfTestB beyond entering the world. If you want this answered later, run the smoke test on a non-warlock with a borrowed payload and observe.

## References

- Forge utility: `scripts/dev/forge_lf_test.py`
- Cleanup utility: `scripts/dev/_cleanup_lf_test.py`
- Fixture A: `tests/fixtures/demon_block_a.bin` (pre-rebind, monster unknown)
- Fixture B: `tests/fixtures/demon_block_b.bin` (post-rebind to fallen)
- Plan reference: `docs/superpowers/plans/2026-04-25-bound-demon-save-block.md` § Phase 0 Task 0.4
