#!/usr/bin/env python3
"""D2R Character Generation CLI.

Usage:
    python3 -m d2r_chargen build <name> [--phase N] [--force]
    python3 -m d2r_chargen import <name> [--force]
    python3 -m d2r_chargen diff <file_a> <file_b>
    python3 -m d2r_chargen list
    python3 -m d2r_chargen validate <name>
    python3 -m d2r_chargen scan <name>
"""
import sys
import os
import argparse


def cmd_build(args):
    from d2r_chargen.character import deploy_character
    deploy_character(args.name, phase=args.phase, force=args.force)
    if getattr(args, 'verify', False):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "d2r_mod", "verify", args.name],
        )
        if result.returncode != 0:
            sys.exit(result.returncode)

def cmd_list(args):
    from d2r_chargen.config import CHARS_DIR
    if not os.path.isdir(CHARS_DIR):
        print(f"No characters directory at {CHARS_DIR}")
        return
    for f in sorted(os.listdir(CHARS_DIR)):
        if f.endswith('.yaml') and f != 'merc_templates.yaml':
            print(f"  {f[:-5]}")

def cmd_validate(args):
    from d2r_chargen.config import CHARS_DIR
    from d2r_chargen.character import load_character_yaml, validate_char_def
    path = os.path.join(CHARS_DIR, f"{args.name}.yaml")
    char_def = load_character_yaml(path)
    validate_char_def(char_def)
    print(f"  {args.name}: YAML validation passed")

    # Binary validation: build to temp, run scanner (Rule 17)
    if not args.yaml_only:
        import shutil
        import struct
        import tempfile
        from d2r_chargen.character import build_all_items
        from d2r_chargen.save import (
            set_character_stats, set_skills,
            rebuild_items, calc_checksum,
        )
        from d2r_chargen.resolve import resolve_skills
        from d2r_chargen.scanner import scan_character_data

        all_items = build_all_items(char_def)
        print(f"  {args.name}: built {len(all_items)} items")

        # Build a temp .d2s with these items for scanner validation
        template_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'data', 'template.d2s'
        )

        saves = os.path.expanduser(
            '~/.local/share/Steam/steamapps/compatdata/2536520/pfx/'
            'drive_c/users/steamuser/Saved Games/Diablo II Resurrected'
        )
        # Prefer existing .d2s as template (has correct status/expansion bits)
        existing_d2s = os.path.join(saves, f"{char_def['name']}.d2s")
        if os.path.exists(existing_d2s):
            template_path = existing_d2s

        with tempfile.NamedTemporaryFile(suffix='.d2s', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            shutil.copy2(template_path, tmp_path)

            data = bytearray(open(tmp_path, 'rb').read())
            skill_array = resolve_skills(char_def['class'], char_def.get('skills', {}))
            stats = char_def['stats']
            data = set_character_stats(
                data, stats['strength'], stats['dexterity'],
                stats['vitality'], stats['energy'],
                level=char_def.get('level', 99),
                char_class=char_def['class'],
                skill_points_spent=sum(skill_array),
            )
            data = set_skills(data, skill_array)
            struct.pack_into('<I', data, 8, len(data))
            data[12:16] = b'\x00\x00\x00\x00'
            cs = calc_checksum(data)
            struct.pack_into('<I', data, 12, cs)
            with open(tmp_path, 'wb') as f:
                f.write(data)

            # Inject all items and run scanner
            item_bytes_list = [item_bytes for _, item_bytes in all_items]
            result_data = rebuild_items(tmp_path, item_bytes_list, [])
            with open(tmp_path, 'wb') as f:
                f.write(result_data)

            scan = scan_character_data(tmp_path)
            errors = scan.get('errors', [])
            warnings = scan.get('warnings', [])

            if errors:
                print(f"  SCANNER ERRORS ({len(errors)}):")
                for err in errors:
                    print(f"    {err}")
                sys.exit(1)
            if warnings:
                for w in warnings:
                    print(f"  WARNING: {w}")

            print(f"  {args.name}: binary validation passed "
                  f"({scan['item_count']} items, checksum {'OK' if scan['checksum_ok'] else 'FAIL'})")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

def cmd_scan(args):
    from d2r_chargen.scanner import run_scanner
    run_scanner(args.name.lower())

def cmd_import(args):
    from d2r_chargen.importer import import_character, dict_to_yaml
    saves = os.path.expanduser(
        '~/.local/share/Steam/steamapps/compatdata/2536520/pfx/'
        'drive_c/users/steamuser/Saved Games/Diablo II Resurrected'
    )
    d2s_path = os.path.join(saves, f"{args.name}.d2s")
    if not os.path.exists(d2s_path):
        print(f"  ERROR: {d2s_path} not found")
        return

    result = import_character(d2s_path)
    yaml_str = dict_to_yaml(result)

    from d2r_chargen.config import CHARS_DIR
    output = os.path.join(CHARS_DIR, f"{args.name}.yaml")
    if os.path.exists(output) and not args.force:
        print(f"  {output} already exists. Use --force to overwrite.")
        return

    with open(output, 'w') as f:
        f.write(yaml_str)
    print(f"  Imported {args.name} → {output}")

def cmd_diff(args):
    from d2r_chargen.diff import diff_saves, format_diff
    result = diff_saves(args.file_a, args.file_b)
    print(format_diff(result))

def main():
    parser = argparse.ArgumentParser(description='D2R Character Generation')
    sub = parser.add_subparsers(dest='command')

    p_build = sub.add_parser('build', help='Build and deploy a character')
    p_build.add_argument('name')
    p_build.add_argument('--phase', type=int, default=4)
    p_build.add_argument('--force', action='store_true', help='Bypass freshness gate')
    p_build.add_argument('--verify', action='store_true',
                         help='After build, launch D2R and verify character joins game')
    p_build.set_defaults(func=cmd_build)

    p_import = sub.add_parser('import', help='Import .d2s to YAML')
    p_import.add_argument('name')
    p_import.add_argument('--force', action='store_true', help='Overwrite existing YAML')
    p_import.set_defaults(func=cmd_import)

    p_diff = sub.add_parser('diff', help='Compare two .d2s files')
    p_diff.add_argument('file_a')
    p_diff.add_argument('file_b')
    p_diff.set_defaults(func=cmd_diff)

    p_list = sub.add_parser('list', help='List defined characters')
    p_list.set_defaults(func=cmd_list)

    p_val = sub.add_parser('validate', help='Validate character YAML and binary encoding')
    p_val.add_argument('name')
    p_val.add_argument('--yaml-only', action='store_true',
                       help='Only validate YAML structure, skip binary build+scan')
    p_val.set_defaults(func=cmd_validate)

    p_scan = sub.add_parser('scan', help='Run d2rdoctor scanner')
    p_scan.add_argument('name')
    p_scan.set_defaults(func=cmd_scan)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    args.func(args)

if __name__ == '__main__':
    main()
