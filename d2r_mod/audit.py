"""D2R skills and items audit: extraction, scoring, ranking, report generation."""

from d2r_mod.calc_parser import eval_expr

# Level bracket boundaries for per-level damage/mana scaling
_BRACKETS = [
    (2, 8, 1),    # levels 2-8  -> LevDam1 (7 levels)
    (9, 16, 2),   # levels 9-16 -> LevDam2 (8 levels)
    (17, 22, 3),  # levels 17-22 -> LevDam3 (6 levels)
    (23, 28, 4),  # levels 23-28 -> LevDam4 (6 levels)
    (29, 999, 5), # levels 29+  -> LevDam5
]


def _int(val: str) -> int:
    """Parse an int from a TSV cell, defaulting to 0."""
    if not val or not val.strip():
        return 0
    try:
        return int(val)
    except ValueError:
        return 0


def _scaled_at_level(base: int, per_level: list[int], level: int) -> float:
    """Compute a level-scaled value (damage or mana) at the given skill level."""
    total = float(base)
    for start, end, idx in _BRACKETS:
        plv = per_level[idx - 1] if idx - 1 < len(per_level) else 0
        if level < start:
            break
        levels_in_bracket = min(level, end) - start + 1
        total += plv * levels_in_bracket
    return total


def compute_damage_at_level(row: dict, level: int) -> tuple[float, float]:
    """Compute (min_damage, max_damage) for a skill at the given level.

    Sums physical (MinDam) and elemental (EMin) damage.
    """
    phys_min = _scaled_at_level(
        _int(row.get("MinDam", "")),
        [_int(row.get(f"MinLevDam{i}", "")) for i in range(1, 6)],
        level,
    )
    phys_max = _scaled_at_level(
        _int(row.get("MaxDam", "")),
        [_int(row.get(f"MaxLevDam{i}", "")) for i in range(1, 6)],
        level,
    )
    elem_min = _scaled_at_level(
        _int(row.get("EMin", "")),
        [_int(row.get(f"EMinLev{i}", "")) for i in range(1, 6)],
        level,
    )
    elem_max = _scaled_at_level(
        _int(row.get("EMax", "")),
        [_int(row.get(f"EMaxLev{i}", "")) for i in range(1, 6)],
        level,
    )
    return phys_min + elem_min, phys_max + elem_max


def compute_mana_at_level(row: dict, level: int) -> float:
    """Compute mana cost at the given skill level."""
    start = _int(row.get("startmana", ""))
    per_level = _int(row.get("lvlmana", ""))
    minimum = _int(row.get("minmana", ""))
    shift = _int(row.get("manashift", ""))
    if shift == 0:
        shift = 8  # default shift
    raw = start + per_level * (level - 1)
    cost = raw >> shift
    return float(max(minimum, cost))


def build_calc_context(row: dict, level: int) -> dict:
    """Build a context dict for eval_expr from a skill row's parameters."""
    ctx: dict = {"lvl": float(level)}
    # Param1-Param20
    for i in range(1, 21):
        ctx[f"par{i}"] = float(_int(row.get(f"Param{i}", "")))
    # ln## interpolations: ln12 = Param1 + Param2*(level-1), etc.
    for pair_idx, suffix in enumerate(["12", "34", "56", "78"], start=0):
        p_base = float(_int(row.get(f"Param{pair_idx * 2 + 1}", "")))
        p_rate = float(_int(row.get(f"Param{pair_idx * 2 + 2}", "")))
        ctx[f"ln{suffix}"] = p_base + p_rate * (level - 1)
    # dm## — approximate from damage columns
    lo, hi = compute_damage_at_level(row, level)
    for suffix in ["12", "34", "56", "78"]:
        ctx[f"dm{suffix}"] = (lo + hi) / 2
    ctx["edmn"] = float(_int(row.get("EMin", "")))
    return ctx


# Class code mapping
CLASS_NAMES = {
    "ama": "Amazon", "sor": "Sorceress", "nec": "Necromancer",
    "pal": "Paladin", "bar": "Barbarian", "dru": "Druid",
    "ass": "Assassin", "wlk": "Warlock",
}


def categorize_skill(row: dict) -> str:
    """Categorize a skill as damage, passive, aura, summon, or utility."""
    if row.get("passive") == "1" or row.get("passivestat1"):
        return "passive"
    if row.get("aura") == "1" or row.get("aurastat1"):
        return "aura"
    if row.get("summon"):
        return "summon"
    if any(_int(row.get(c, "")) for c in ("MinDam", "MaxDam", "EMin", "EMax")):
        return "damage"
    return "utility"


def audit_skills(tables: dict, eval_level: int = 20) -> list[dict]:
    """Audit all skills. Returns ranked list with damage, mana, and flags."""
    skills = tables["data/global/excel/Skills.txt"]
    results = []

    for row in skills:
        name = row.get("skill", "")
        charclass = row.get("charclass", "")
        if not name or not charclass or row.get("InGame") != "1":
            continue

        category = categorize_skill(row)
        lo, hi = compute_damage_at_level(row, eval_level)
        mana = compute_mana_at_level(row, eval_level)

        # Apply synergy calc if present
        ctx = build_calc_context(row, eval_level)
        ctx["skill_levels"] = {}  # base evaluation, no synergies invested
        for calc_col in ("EDmgSymPerCalc", "DmgSymPerCalc"):
            expr = row.get(calc_col, "")
            if expr:
                try:
                    bonus_pct = eval_expr(expr, ctx)
                except (ValueError, IndexError):
                    bonus_pct = 0  # unparseable expression, skip
                lo *= (1 + bonus_pct / 100)
                hi *= (1 + bonus_pct / 100)

        avg_damage = (lo + hi) / 2
        dpm = avg_damage / mana if mana > 0 else avg_damage

        results.append({
            "skill": name,
            "charclass": charclass,
            "class_name": CLASS_NAMES.get(charclass, charclass),
            "category": category,
            "damage_lo": lo,
            "damage_hi": hi,
            "damage_avg": avg_damage,
            "mana_cost": mana,
            "damage_per_mana": dpm,
            "flagged": False,
            "flag_reason": "",
        })

    # Rank within class and flag bottom quartile of damage skills
    for charclass in set(r["charclass"] for r in results):
        class_damage = sorted(
            [r for r in results if r["charclass"] == charclass and r["category"] == "damage"],
            key=lambda r: r["damage_per_mana"],
            reverse=True,
        )
        if not class_damage:
            continue
        best = class_damage[0]["damage_per_mana"]
        for i, r in enumerate(class_damage):
            r["rank_in_class"] = i + 1
            if best > 0 and r["damage_per_mana"] < best * 0.25:
                r["flagged"] = True
                r["flag_reason"] = f"<25% of best ({r['damage_per_mana']:.1f} vs {best:.1f})"

    # Sort by class then rank
    results.sort(key=lambda r: (r["charclass"], -r["damage_per_mana"]))
    return results


def extract_item_stats(row: dict, prefix: str = "prop", count: int = 12,
                       par_prefix: str = "par", min_prefix: str = "min",
                       max_prefix: str = "max") -> list[dict]:
    """Extract stat properties from an item row."""
    stats = []
    for i in range(1, count + 1):
        prop = row.get(f"{prefix}{i}", "")
        if not prop:
            continue
        stats.append({
            "prop": prop,
            "par": row.get(f"{par_prefix}{i}", ""),
            "min": _int(row.get(f"{min_prefix}{i}", "")),
            "max": _int(row.get(f"{max_prefix}{i}", "")),
        })
    return stats


def derive_stat_weights(items: list[dict], min_level: int = 60) -> dict[str, float]:
    """Derive empirical stat weights from endgame items."""
    weights: dict[str, float] = {}
    for item in items:
        if item.get("level", 0) < min_level:
            continue
        for stat in item.get("stats", []):
            val = max(abs(stat["min"]), abs(stat["max"]))
            prop = stat["prop"]
            if val > weights.get(prop, 0):
                weights[prop] = float(val)
    return weights


def score_item(stats: list[dict], weights: dict[str, float]) -> float:
    """Score an item using normalized stat values."""
    total = 0.0
    for stat in stats:
        prop = stat["prop"]
        val = max(abs(stat["min"]), abs(stat["max"]))
        w = weights.get(prop, 0)
        if w > 0:
            total += val / w
    return total


def audit_items(tables: dict) -> list[dict]:
    """Audit all items. Returns scored/ranked list with flags."""
    all_items = []

    # Uniques
    for row in tables.get("data/global/excel/UniqueItems.txt", []):
        if row.get("disabled") == "1" or not row.get("index"):
            continue
        stats = extract_item_stats(row, "prop", 12)
        all_items.append({
            "name": row["index"],
            "type": "unique",
            "level": _int(row.get("lvl req", row.get("lvl", ""))),
            "stats": stats,
        })

    # Set items
    for row in tables.get("data/global/excel/SetItems.txt", []):
        if row.get("disabled") == "1" or not row.get("index"):
            continue
        stats = extract_item_stats(row, "prop", 9)
        all_items.append({
            "name": row["index"],
            "type": "set",
            "level": _int(row.get("lvl req", row.get("lvl", ""))),
            "stats": stats,
        })

    # Runewords
    for row in tables.get("data/global/excel/Runes.txt", []):
        if not row.get("Name") or row.get("complete") != "1":
            continue
        stats = extract_item_stats(row, "T1Code", 7, "T1Param", "T1Min", "T1Max")
        all_items.append({
            "name": row.get("*Rune Name", row["Name"]),
            "type": "runeword",
            "level": 0,
            "stats": stats,
        })

    # Derive weights from endgame items
    weights = derive_stat_weights(all_items, min_level=60)

    # Score each item
    for item in all_items:
        item["score"] = score_item(item["stats"], weights)

    # Assign level brackets and flag weak items
    brackets = [(0, 30, "low"), (31, 60, "mid"), (61, 999, "endgame")]
    for b_lo, b_hi, b_name in brackets:
        bracket_items = [it for it in all_items if b_lo <= it["level"] <= b_hi]
        if not bracket_items:
            continue
        scores = sorted([it["score"] for it in bracket_items])
        median = scores[len(scores) // 2] if scores else 0
        for item in bracket_items:
            item["bracket"] = b_name
            item["flagged"] = False
            item["flag_reason"] = ""
            if median > 0 and item["score"] < median * 0.4:
                item["flagged"] = True
                item["flag_reason"] = f"Score {item['score']:.2f} < 40% of median {median:.2f}"

    all_items.sort(key=lambda it: (it.get("bracket", ""), -it["score"]))
    return all_items


def generate_skills_report(results: list[dict]) -> str:
    """Generate markdown skills audit report."""
    lines = ["# Skills Audit Report", "",
             f"Evaluated at skill level 20. Flagged = <25% of best damage-per-mana in class.", ""]

    by_class: dict[str, list[dict]] = {}
    for r in results:
        by_class.setdefault(r["class_name"], []).append(r)

    for class_name in sorted(by_class):
        lines.append(f"## {class_name}")
        lines.append("")
        lines.append("| Rank | Skill | Category | Avg Damage | Mana | DPM | Flag |")
        lines.append("|------|-------|----------|-----------|------|-----|------|")
        for r in by_class[class_name]:
            flag = f"**{r['flag_reason']}**" if r["flagged"] else ""
            rank = r.get("rank_in_class", "-")
            lines.append(
                f"| {rank} | {r['skill']} | {r['category']} | "
                f"{r['damage_avg']:.0f} | {r['mana_cost']:.0f} | "
                f"{r['damage_per_mana']:.1f} | {flag} |"
            )
        lines.append("")

    return "\n".join(lines)


def generate_items_report(results: list[dict]) -> str:
    """Generate markdown items audit report."""
    lines = ["# Items Audit Report", "",
             "Scored by normalized stat budget. Flagged = <40% of bracket median.", ""]

    by_bracket: dict[str, list[dict]] = {}
    for r in results:
        by_bracket.setdefault(r.get("bracket", "unknown"), []).append(r)

    for bracket in ("low", "mid", "endgame"):
        items = by_bracket.get(bracket, [])
        if not items:
            continue
        lvl_range = '1-30' if bracket == 'low' else '31-60' if bracket == 'mid' else '60+'
        lines.append(f"## {bracket.title()} Tier [{bracket}] (lvl {lvl_range})")
        lines.append("")
        lines.append("| Name | Type | Lvl | Score | Flag |")
        lines.append("|------|------|-----|-------|------|")
        for r in items:
            flag = f"**{r['flag_reason']}**" if r["flagged"] else ""
            lines.append(f"| {r['name']} | {r['type']} | {r['level']} | {r['score']:.2f} | {flag} |")
        lines.append("")

    return "\n".join(lines)
