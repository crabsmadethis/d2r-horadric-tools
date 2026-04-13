"""CLI entry point for d2r-mod commands."""

import argparse
import os
import sys
import shutil

from d2r_mod.build import build_mod, DEFAULT_GAME_DIR


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="d2r-mod",
        description="D2R mod data pipeline",
    )
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    p_build = sub.add_parser("build", help="Build mod from vanilla + overlays + scripts")
    p_build.add_argument("--warn-conflicts", action="store_true",
                         help="Warn when two overlays touch the same cell")
    p_build.add_argument("--no-regen", action="store_true",
                         help="Skip chargen data regeneration")
    p_build.add_argument("--game-dir", default=DEFAULT_GAME_DIR)

    p_deploy = sub.add_parser("deploy", help="Build + deploy mod to game mod folder")
    p_deploy.add_argument("--game-dir", default=DEFAULT_GAME_DIR)
    p_deploy.add_argument("--force", action="store_true",
                          help="Deploy even if vanilla data is stale")
    p_deploy.add_argument("--no-casc", action="store_true",
                          help="Skip CASC injection of modified JSON files")
    p_deploy.add_argument("--no-build", action="store_true",
                          help="Skip rebuild (deploy existing build/ as-is)")
    p_deploy.add_argument("--warn-conflicts", action="store_true",
                          help="Warn when two overlays touch the same cell")
    p_deploy.add_argument("--no-regen", action="store_true",
                          help="Skip chargen data regeneration")

    p_undeploy = sub.add_parser("undeploy", help="Remove mod from game")
    p_undeploy.add_argument("--game-dir", default=DEFAULT_GAME_DIR)
    p_undeploy.add_argument("--keep-mod", action="store_true",
                            help="Keep mod files, only remove patcher artifacts and launch options")

    sub.add_parser("clean", help="Remove build/ and reset chargen data")

    p_extract = sub.add_parser("extract", help="Extract vanilla data from CASC archive")
    p_extract.add_argument("--game-dir", default=DEFAULT_GAME_DIR)

    p_update = sub.add_parser("update", help="Re-extract, rebuild, and redeploy (recovery after game update)")
    p_update.add_argument("--game-dir", default=DEFAULT_GAME_DIR)
    p_update.add_argument("--warn-conflicts", action="store_true",
                          help="Warn when two overlays touch the same cell")
    p_update.add_argument("--no-regen", action="store_true",
                          help="Skip chargen data regeneration")

    p_diff = sub.add_parser("diff", help="Compare vanilla vs build")
    p_diff.add_argument("file", nargs="?", default=None,
                        help="Specific .txt file to diff (basename match)")
    p_diff.add_argument("--summary", action="store_true",
                        help="One-line summary per file")

    p_inject = sub.add_parser("inject", help="Inject files into CASC archive")
    p_inject.add_argument("virtual_path", nargs="?",
                          help="TVFS path (e.g., data/global/ui/layouts/hudpanelhd.json)")
    p_inject.add_argument("source", nargs="?",
                          help="Local file to inject")
    p_inject.add_argument("--from-dir",
                          help="Inject all files from directory")
    p_inject.add_argument("--prefix", default="",
                          help="Virtual path prefix for --from-dir")
    p_inject.add_argument("--dry-run", action="store_true",
                          help="Show what would be injected")
    p_inject.add_argument("--game-dir", default=DEFAULT_GAME_DIR)

    p_audit = sub.add_parser("audit", help="Audit vanilla skills and items")
    p_audit.add_argument("--skills", action="store_true", help="Run skills audit")
    p_audit.add_argument("--items", action="store_true", help="Run items audit")
    p_audit.add_argument("--all", action="store_true", help="Run full audit")
    p_audit.add_argument("--output-dir", default=os.path.join(_project_root(), "docs", "audit"),
                         help="Directory to save reports")

    try:
        import d2r_mod.verify  # noqa: F401
        p_verify = sub.add_parser("verify", help="Verify character can join a game")
        p_verify.add_argument("name", help="Character name")
        p_verify.add_argument("--difficulty", choices=["normal", "nightmare", "hell"],
                               default=None, help="Override auto-detected difficulty")
        p_verify.add_argument("--position", type=int, default=None,
                               help="Override character position in list (0-indexed, bypasses mtime detection)")
        p_verify.add_argument("--no-exit", action="store_true",
                               help="Stay in-game after verification")
    except ImportError:
        pass

    try:
        from d2r_mod.engine.cli import add_engine_subparser
        add_engine_subparser(sub)
    except ImportError:
        pass

    try:
        from d2r_mod.host.cli import add_host_subparser
        add_host_subparser(sub)
    except ImportError:
        pass

    return parser.parse_args(argv)


def cmd_build(args: argparse.Namespace) -> None:
    root = _project_root()
    warnings = build_mod(
        vanilla_dir=os.path.join(root, "vanilla"),
        overlays_dir=os.path.join(root, "overlays"),
        scripts_dir=os.path.join(root, "scripts"),
        build_dir=os.path.join(root, "build"),
        regen=not args.no_regen,
        game_dir=args.game_dir,
        warn_conflicts=args.warn_conflicts,
    )
    if warnings:
        for w in warnings:
            print(f"WARNING: {w}")
    print("Build complete.")


def cmd_deploy(args: argparse.Namespace) -> None:
    from d2r_mod.deploy import deploy_mod, deploy_casc, verify_deploy
    root = _project_root()
    build_dir = os.path.join(root, "build")
    vanilla_dir = os.path.join(root, "vanilla")

    # Build first unless --no-build
    if not args.no_build:
        print("Building...")
        warnings = build_mod(
            vanilla_dir=vanilla_dir,
            overlays_dir=os.path.join(root, "overlays"),
            scripts_dir=os.path.join(root, "scripts"),
            build_dir=build_dir,
            regen=not args.no_regen,
            game_dir=args.game_dir,
            warn_conflicts=args.warn_conflicts,
        )
        if warnings:
            for w in warnings:
                print(f"  WARNING: {w}")
        print("Build complete.")

    # Deploy TSV/TBL via mod directory (-mod -txt)
    deploy_mod(
        build_dir,
        args.game_dir,
        force=args.force,
        vanilla_dir=vanilla_dir,
    )

    # Deploy modified JSON via CASC injection
    if not args.no_casc:
        deploy_casc(build_dir, vanilla_dir, args.game_dir)

    # Verify key files match between build/ and deployed mod
    verify_deploy(build_dir, args.game_dir)


def cmd_undeploy(args: argparse.Namespace) -> None:
    from d2r_mod.deploy import undeploy_mod
    undeploy_mod(args.game_dir, keep_mod=getattr(args, "keep_mod", False))


def cmd_clean(args: argparse.Namespace) -> None:
    root = _project_root()
    build_dir = os.path.join(root, "build")

    vanilla_dir = os.path.join(root, "vanilla")
    if os.path.isdir(vanilla_dir):
        from d2r_mod.regen import regen_all
        regen_all(vanilla_dir)
        print("Reset chargen data to vanilla values.")
    else:
        print("WARNING: vanilla/ not found — chargen data not reset.")

    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
        print(f"Removed {build_dir}")
    else:
        print("No build/ to remove.")


def cmd_extract(args: argparse.Namespace) -> None:
    from d2r_mod.casc import extract_vanilla, _parse_build_info
    from d2r_mod.version import write_vanilla_version
    from d2r_mod.regen import regen_all
    root = _project_root()
    output_dir = os.path.join(root, "vanilla")
    result = extract_vanilla(args.game_dir, output_dir)
    build_key = _parse_build_info(args.game_dir)
    write_vanilla_version(output_dir, build_key)
    print(f"Extracted {len(result)} files to {output_dir}")
    regen_all(output_dir)
    print("Regenerated chargen data files.")


def cmd_audit(args: argparse.Namespace) -> None:
    from d2r_mod.tsv import read_tsv_file
    from d2r_mod.audit import (
        audit_skills, audit_items,
        generate_skills_report, generate_items_report,
    )
    root = _project_root()
    vanilla_dir = os.path.join(root, "vanilla")

    tables = {}
    excel_dir = os.path.join(vanilla_dir, "data", "global", "excel")
    for fname in os.listdir(excel_dir):
        if fname.endswith(".txt"):
            key = f"data/global/excel/{fname}"
            tables[key] = read_tsv_file(os.path.join(excel_dir, fname))

    os.makedirs(args.output_dir, exist_ok=True)

    if args.skills or args.all:
        results = audit_skills(tables)
        report = generate_skills_report(results)
        path = os.path.join(args.output_dir, "skills_report.md")
        with open(path, "w") as f:
            f.write(report)
        flagged = sum(1 for r in results if r["flagged"])
        print(f"Skills audit: {len(results)} skills, {flagged} flagged. Report: {path}")

    if args.items or args.all:
        results = audit_items(tables)
        report = generate_items_report(results)
        path = os.path.join(args.output_dir, "items_report.md")
        with open(path, "w") as f:
            f.write(report)
        flagged = sum(1 for r in results if r["flagged"])
        print(f"Items audit: {len(results)} items, {flagged} flagged. Report: {path}")


def cmd_verify(args: argparse.Namespace) -> None:
    from d2r_mod.verify import verify_character
    result = verify_character(
        args.name,
        difficulty=args.difficulty,
        position=args.position,
        no_exit=args.no_exit,
    )
    sys.exit(result)


def cmd_update(args: argparse.Namespace) -> None:
    """Run the full recovery pipeline: extract → build → deploy."""
    from d2r_mod.casc import extract_vanilla, _parse_build_info
    from d2r_mod.version import write_vanilla_version
    from d2r_mod.deploy import deploy_mod, deploy_casc

    root = _project_root()
    vanilla_dir = os.path.join(root, "vanilla")
    build_dir = os.path.join(root, "build")

    # Phase 1: Extract
    print("=== Phase 1/3: Extract ===")
    result = extract_vanilla(args.game_dir, vanilla_dir)
    build_key = _parse_build_info(args.game_dir)
    write_vanilla_version(vanilla_dir, build_key)
    print(f"Extracted {len(result)} files to {vanilla_dir}")

    # Phase 2: Build
    print("\n=== Phase 2/3: Build ===")
    warnings = build_mod(
        vanilla_dir=vanilla_dir,
        overlays_dir=os.path.join(root, "overlays"),
        scripts_dir=os.path.join(root, "scripts"),
        build_dir=build_dir,
        regen=not args.no_regen,
        game_dir=args.game_dir,
        warn_conflicts=args.warn_conflicts,
    )
    if warnings:
        for w in warnings:
            print(f"WARNING: {w}")
    print("Build complete.")

    # Phase 3: Deploy (force=True since we just extracted fresh data)
    print("\n=== Phase 3/4: Deploy mod files ===")
    deploy_mod(build_dir, args.game_dir, force=True, vanilla_dir=vanilla_dir)

    # Phase 4: CASC injection for modified JSON
    print("\n=== Phase 4/4: CASC injection ===")
    deploy_casc(build_dir, vanilla_dir, args.game_dir)
    print("\nUpdate complete. Restart D2R for changes to take effect.")


def cmd_engine(args: argparse.Namespace) -> None:
    from d2r_mod.engine.cli import cmd_analyze, cmd_strings, cmd_report
    handlers = {
        "analyze": cmd_analyze,
        "strings": cmd_strings,
        "report": cmd_report,
    }
    handlers[args.engine_command](args)


def cmd_inject(args: argparse.Namespace) -> None:
    from d2r_mod.casc_write import inject_files

    file_map = {}

    if args.from_dir:
        # Inject all files from a directory
        base_dir = args.from_dir
        prefix = args.prefix.rstrip("/")
        for dirpath, _, filenames in os.walk(base_dir):
            for fname in filenames:
                local = os.path.join(dirpath, fname)
                rel = os.path.relpath(local, base_dir)
                vpath = f"{prefix}/{rel}" if prefix else rel
                vpath = vpath.replace(os.sep, "/")
                with open(local, "rb") as f:
                    file_map[vpath] = f.read()
    elif args.virtual_path and args.source:
        with open(args.source, "rb") as f:
            file_map[args.virtual_path] = f.read()
    else:
        print("Usage: d2r-mod inject <virtual_path> <source>")
        print("   or: d2r-mod inject --from-dir <dir> --prefix <prefix>")
        sys.exit(1)

    if args.dry_run:
        print(f"Would inject {len(file_map)} file(s):")
        for vpath, content in file_map.items():
            print(f"  {vpath} ({len(content)} bytes)")
        return

    print(f"Injecting {len(file_map)} file(s) into CASC...")
    result = inject_files(args.game_dir, file_map)

    for item in result["injected"]:
        print(f"  {item['path']}: ekey={item['ekey'][:18]}...")
    print(f"Created {len(result['idx_files'])} .idx file(s)")
    print(f"New Build Key: {result['new_build_key']}")
    print(f"New TVFS EKey: {result['tvfs_ekey']}")
    print("\nRestart D2R for changes to take effect.")


def cmd_host(args: argparse.Namespace) -> None:
    from d2r_mod.host.cli import cmd_dump, cmd_scan, cmd_patch, cmd_guards, cmd_status, cmd_analyze
    handlers = {
        "dump": cmd_dump,
        "scan": cmd_scan,
        "patch": cmd_patch,
        "guards": cmd_guards,
        "analyze": cmd_analyze,
        "status": cmd_status,
    }
    handlers[args.host_command](args)


def cmd_play(args: argparse.Namespace) -> None:
    from d2r_mod.host.cli import cmd_play as _cmd_play
    _cmd_play(args)


def cmd_diff(args: argparse.Namespace) -> None:
    from d2r_mod.tsv import read_tsv_file
    from d2r_mod.diff import diff_tables, format_diff, summarize_diff

    root = _project_root()
    vanilla_dir = os.path.join(root, "vanilla")
    build_dir = os.path.join(root, "build")

    if not os.path.isdir(vanilla_dir) or not os.path.isdir(build_dir):
        print("Both vanilla/ and build/ must exist. Run 'd2r-mod build' first.")
        sys.exit(1)

    changed_count = 0
    for dirpath, _, filenames in os.walk(vanilla_dir):
        for fname in sorted(filenames):
            if not fname.endswith(".txt"):
                continue
            if args.file and args.file.lower() != fname.lower():
                continue

            v_path = os.path.join(dirpath, fname)
            rel = os.path.relpath(v_path, vanilla_dir)
            b_path = os.path.join(build_dir, rel)

            if not os.path.exists(b_path):
                continue

            v_rows = read_tsv_file(v_path)
            b_rows = read_tsv_file(b_path)
            changes = diff_tables(v_rows, b_rows)

            if not changes:
                continue

            changed_count += 1
            if args.summary:
                print(summarize_diff(fname, changes))
            else:
                print(format_diff(fname, changes))
                print()

    if args.summary:
        print(f"\n{changed_count} file(s) with changes")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    cmd = {
        "build": cmd_build,
        "deploy": cmd_deploy,
        "undeploy": cmd_undeploy,
        "clean": cmd_clean,
        "extract": cmd_extract,
        "update": cmd_update,
        "diff": cmd_diff,
        "audit": cmd_audit,
        "inject": cmd_inject,
    }
    # Optional commands — only available when modules are present
    try:
        from d2r_mod.verify import verify_character  # noqa: F401
        cmd["verify"] = cmd_verify
    except ImportError:
        pass
    try:
        from d2r_mod.engine.cli import cmd_analyze  # noqa: F401
        cmd["engine"] = cmd_engine
    except ImportError:
        pass
    try:
        from d2r_mod.host.cli import cmd_play as _cp  # noqa: F401
        cmd["play"] = cmd_play
        cmd["host"] = cmd_host
    except ImportError:
        pass

    if args.command is None:
        parse_args(["--help"])
    cmd[args.command](args)
