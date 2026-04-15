"""D2R game data tables extracted from game files."""
import importlib.util
import sys

# Generated modules that users must produce via 'd2r-mod extract'
_GENERATED_MODULES = [
    "d2r_chargen.data.item_stat_cost",
    "d2r_chargen.data.item_bases",
    "d2r_chargen.data.item_dimensions",
    "d2r_chargen.data.runewords",
    "d2r_chargen.data.runeword_stats",
    "d2r_chargen.data.unique_items",
    "d2r_chargen.data.unique_item_stats",
    "d2r_chargen.data.set_items",
    "d2r_chargen.data.skills",
]


def data_available() -> bool:
    """Return True if all generated data files exist."""
    for mod in _GENERATED_MODULES:
        if importlib.util.find_spec(mod) is None:
            return False
    return True


def check_data_available():
    """Verify generated data files exist; exit with helpful message if not."""
    missing = []
    for mod in _GENERATED_MODULES:
        if importlib.util.find_spec(mod) is None:
            missing.append(mod.split(".")[-1])
    if missing:
        print(
            f"\nError: Game data files not found: {', '.join(missing)}\n"
            "Run 'd2r-mod extract' first to generate data from your D2R installation.\n"
            "See README.md for setup instructions.",
            file=sys.stderr,
        )
        raise SystemExit(1)
