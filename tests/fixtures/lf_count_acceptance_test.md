# `follower_count=1` Acceptance Summary

This note records the stable public finding from a local manual validation run.
The raw saves and local paths are intentionally not part of this repository.

**Hypothesis:** D2R rejects `follower_count=1` only when the 116-byte follower
payload is missing.

## Method

Two staged saves were derived from the same baseline:

| Variant | `follower_count` | Payload | Expected |
| --- | --- | --- | --- |
| A | 1 | none | reject |
| B | 1 | one 116-byte bound-demon payload | accept |

Both were scanned before promotion. D2R was fully relaunched between file
changes.

## Result

| Variant | Outcome |
| --- | --- |
| A | Rejected at join. |
| B | Loaded successfully and wrote companion cache files. |

## Conclusion

The tested acceptance rule is:

```
follower_count == N  ⇒  exactly N follower payloads must follow
```

For `N == 1` (the only currently-supported case), this means exactly 116 bytes
of demon-block payload after the `lf<u16>` marker.

### Implications for the writer (Phase 3)

1. When chargen builds a Warlock **without** `bound_demon:` YAML → write `follower_count = 0`, no payload. (Status quo.)
2. When chargen builds a Warlock **with** `bound_demon: {template: ...}` → write `follower_count = 1` AND the full 116-byte payload from the template fixture.
3. Round-trip-preserve mode → copy the existing follower block bytes verbatim (count + payload together).
4. **Never write `follower_count >= 1` without the payload.**

## References

- Current public summary: `docs/d2s_format.md` follower block section.
