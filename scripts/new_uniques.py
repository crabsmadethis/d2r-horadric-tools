"""Append custom unique items that fill archetype gaps.

The rows here are part of the public data-mod build pipeline.  They are kept as
source instead of checked-in generated lookup data so a local `d2r-mod build`
can rebuild `UniqueItems.txt`, refresh chargen lookup modules, and register the
custom display names in `expansionstring.tbl`.
"""

CUSTOM_UNIQUE_START_ID = 438


NEW_ITEMS = [
    {
        "index": "Flamekeeper's Antlers",
        "version": "100",
        "disabled": "",
        "spawnable": "1",
        "rarity": "1",
        "nolimit": "",
        "lvl": "84",
        "lvl req": "72",
        "code": "drf",
        "*ItemName": "dream spirit",
        "cost mult": "5",
        "cost add": "5000",
        "chrtransform": "oran",
        "invtransform": "oran",
        "prop1": "skilltab",
        "par1": "16",
        "min1": "3",
        "max1": "3",
        "prop2": "fcr",
        "par2": "",
        "min2": "20",
        "max2": "20",
        "prop3": "dmg-fire",
        "par3": "",
        "min3": "30",
        "max3": "60",
        "prop4": "pierce-fire",
        "par4": "",
        "min4": "15",
        "max4": "15",
        "prop5": "enr",
        "par5": "",
        "min5": "20",
        "max5": "20",
        "prop6": "hp",
        "par6": "",
        "min6": "80",
        "max6": "100",
        "prop7": "res-all",
        "par7": "",
        "min7": "15",
        "max7": "25",
        "*eol": "0",
    },
    {
        "index": "Thunderhurler's Grip",
        "version": "100",
        "disabled": "",
        "spawnable": "1",
        "rarity": "1",
        "nolimit": "",
        "lvl": "80",
        "lvl req": "68",
        "code": "uhg",
        "*ItemName": "ogre gauntlets",
        "cost mult": "5",
        "cost add": "5000",
        "chrtransform": "whit",
        "invtransform": "whit",
        "prop1": "skill",
        "par1": "Throwing Mastery",
        "min1": "3",
        "max1": "3",
        "prop2": "swing2",
        "par2": "",
        "min2": "20",
        "max2": "20",
        "prop3": "dmg%",
        "par3": "",
        "min3": "80",
        "max3": "120",
        "prop4": "dex",
        "par4": "",
        "min4": "25",
        "max4": "30",
        "prop5": "str",
        "par5": "",
        "min5": "15",
        "max5": "20",
        "prop6": "regen-stam",
        "par6": "",
        "min6": "15",
        "max6": "20",
        "*eol": "0",
    },
    {
        "index": "Hawkeye's Sight",
        "version": "100",
        "disabled": "",
        "spawnable": "1",
        "rarity": "1",
        "nolimit": "",
        "lvl": "80",
        "lvl req": "68",
        "code": "ci3",
        "*ItemName": "diadem",
        "cost mult": "5",
        "cost add": "5000",
        "chrtransform": "bwht",
        "invtransform": "bwht",
        "prop1": "skilltab",
        "par1": "0",
        "min1": "3",
        "max1": "3",
        "prop2": "ignore-ac",
        "par2": "1",
        "min2": "1",
        "max2": "1",
        "prop3": "swing2",
        "par3": "",
        "min3": "20",
        "max3": "20",
        "prop4": "att",
        "par4": "",
        "min4": "150",
        "max4": "200",
        "prop5": "dex",
        "par5": "",
        "min5": "25",
        "max5": "30",
        "prop6": "move2",
        "par6": "",
        "min6": "20",
        "max6": "30",
        "prop7": "gold%",
        "par7": "",
        "min7": "40",
        "max7": "60",
        "*eol": "0",
    },
    {
        "index": "Deathgrip Scepter",
        "version": "100",
        "disabled": "",
        "spawnable": "1",
        "rarity": "1",
        "nolimit": "",
        "lvl": "82",
        "lvl req": "69",
        "code": "7gw",
        "*ItemName": "unearthed wand",
        "cost mult": "5",
        "cost add": "5000",
        "chrtransform": "whit",
        "invtransform": "whit",
        "prop1": "skilltab",
        "par1": "8",
        "min1": "3",
        "max1": "3",
        "prop2": "skill",
        "par2": "Skeleton Mastery",
        "min2": "3",
        "max2": "3",
        "prop3": "fcr",
        "par3": "",
        "min3": "30",
        "max3": "30",
        "prop4": "dmg%",
        "par4": "",
        "min4": "20",
        "max4": "40",
        "prop5": "enr",
        "par5": "",
        "min5": "15",
        "max5": "20",
        "prop6": "mana",
        "par6": "",
        "min6": "60",
        "max6": "80",
        "prop7": "regen",
        "par7": "",
        "min7": "8",
        "max7": "12",
        "*eol": "0",
    },
    {
        "index": "Crusader's Vengeance",
        "version": "100",
        "disabled": "",
        "spawnable": "1",
        "rarity": "1",
        "nolimit": "",
        "lvl": "82",
        "lvl req": "70",
        "code": "7cr",
        "*ItemName": "phase blade",
        "cost mult": "5",
        "cost add": "5000",
        "chrtransform": "gold",
        "invtransform": "gold",
        "prop1": "ignore-ac",
        "par1": "1",
        "min1": "1",
        "max1": "1",
        "prop2": "skilltab",
        "par2": "9",
        "min2": "3",
        "max2": "3",
        "prop3": "dmg%",
        "par3": "",
        "min3": "180",
        "max3": "220",
        "prop4": "dmg-fire",
        "par4": "",
        "min4": "50",
        "max4": "100",
        "prop5": "dmg-ltng",
        "par5": "",
        "min5": "1",
        "max5": "150",
        "prop6": "dmg-cold",
        "par6": "4",
        "min6": "25",
        "max6": "75",
        "prop7": "swing2",
        "par7": "",
        "min7": "20",
        "max7": "20",
        "prop8": "res-all",
        "par8": "",
        "min8": "10",
        "max8": "20",
        "*eol": "0",
    },
    {
        "index": "Manoomin",
        "version": "100",
        "disabled": "",
        "spawnable": "1",
        "rarity": "1",
        "nolimit": "",
        "lvl": "1",
        "lvl req": "1",
        "code": "cm1",
        "*ItemName": "small charm",
        "cost mult": "1",
        "cost add": "0",
        "chrtransform": "cgrn",
        "invtransform": "cgrn",
        "prop1": "regen",
        "par1": "",
        "min1": "10",
        "max1": "10",
        "prop2": "hp",
        "par2": "",
        "min2": "20",
        "max2": "20",
        "prop3": "res-cold",
        "par3": "",
        "min3": "15",
        "max3": "15",
        "prop4": "res-pois",
        "par4": "",
        "min4": "15",
        "max4": "15",
        "prop5": "stam",
        "par5": "",
        "min5": "30",
        "max5": "30",
        "*eol": "0",
    },
]


def _existing_ids(rows):
    ids = {}
    for row in rows:
        id_value = str(row.get("*ID", "")).strip()
        if id_value.isdigit():
            ids[int(id_value)] = row.get("index", "")
    return ids


def apply(tables):
    """Append the custom unique rows to UniqueItems.txt."""
    key = "data/global/excel/UniqueItems.txt"
    uniques = tables[key]
    template = {k: "" for k in uniques[0].keys()} if uniques else {}
    existing_ids = _existing_ids(uniques)
    existing_name_to_id = {
        row.get("index", ""): int(str(row.get("*ID", "")).strip())
        for row in uniques
        if str(row.get("*ID", "")).strip().isdigit()
    }

    warnings = []
    for offset, item in enumerate(NEW_ITEMS):
        item_id = CUSTOM_UNIQUE_START_ID + offset
        name = item["index"]
        existing_id_name = existing_ids.get(item_id)
        existing_name_id = existing_name_to_id.get(name)

        if existing_name_id is not None:
            if existing_name_id != item_id:
                raise ValueError(
                    f"Cannot add {name}: existing row uses *ID {existing_name_id}, "
                    f"expected {item_id}"
                )
            warnings.append(f"Skipped existing unique: {name} (*ID={item_id})")
            continue
        if existing_id_name:
            raise ValueError(
                f"Cannot add {name}: UniqueItems.txt *ID {item_id} "
                f"is already used by {existing_id_name}"
            )

        row = dict(template)
        row.update(item)
        row["*ID"] = str(item_id)
        uniques.append(row)
        existing_ids[item_id] = name
        existing_name_to_id[name] = item_id
        warnings.append(f"Added unique: {name} (code={item['code']}, *ID={item_id})")

    return warnings
