"""d2r_mod command wrappers for d2r_mcp.

Each tool runs the corresponding d2r_mod operation and returns a
structured envelope. Long-running commands (extract, update) are still
synchronous — D2R mod builds finish in seconds.
"""
import os

from d2r_mcp.envelope import ok, error


def _project_root() -> str:
    """Same as d2r_mod.cli._project_root — one level up from d2r_mod/."""
    import d2r_mod
    return os.path.dirname(os.path.dirname(os.path.abspath(d2r_mod.__file__)))


def build(warn_conflicts: bool = False, no_regen: bool = False,
          game_dir: str | None = None) -> dict:
    """Build mod from vanilla + overlays + scripts.

    Returns envelope with captured warnings from build_mod.
    """
    from d2r_mod.build import build_mod, DEFAULT_GAME_DIR as _DEFAULT
    root = _project_root()
    try:
        warnings = build_mod(
            vanilla_dir=os.path.join(root, "vanilla"),
            overlays_dir=os.path.join(root, "overlays"),
            scripts_dir=os.path.join(root, "scripts"),
            build_dir=os.path.join(root, "build"),
            regen=not no_regen,
            game_dir=game_dir or _DEFAULT,
            warn_conflicts=warn_conflicts,
        )
    except FileNotFoundError as ex:
        return error("missing_dir", str(ex))
    except Exception as ex:
        return error("build_exception", f"{type(ex).__name__}: {ex}")
    return ok(warnings=list(warnings) if warnings else [],
              build_dir=os.path.join(root, "build"))


def deploy(force: bool = False, no_casc: bool = False, no_build: bool = False,
           warn_conflicts: bool = False, no_regen: bool = False,
           game_dir: str | None = None) -> dict:
    """Build + deploy mod to the game mod folder."""
    from d2r_mod.build import build_mod, DEFAULT_GAME_DIR as _DEFAULT
    from d2r_mod.deploy import deploy_mod, deploy_casc, verify_deploy
    root = _project_root()
    gdir = game_dir or _DEFAULT
    build_dir = os.path.join(root, "build")
    vanilla_dir = os.path.join(root, "vanilla")
    warnings = []
    try:
        if not no_build:
            ws = build_mod(
                vanilla_dir=vanilla_dir,
                overlays_dir=os.path.join(root, "overlays"),
                scripts_dir=os.path.join(root, "scripts"),
                build_dir=build_dir,
                regen=not no_regen,
                game_dir=gdir,
                warn_conflicts=warn_conflicts,
            )
            if ws:
                warnings.extend(ws)
        deploy_mod(build_dir, gdir, force=force, vanilla_dir=vanilla_dir)
        if not no_casc:
            deploy_casc(build_dir, vanilla_dir, gdir)
        verify_deploy(build_dir, gdir)
    except FileNotFoundError as ex:
        return error("missing_dir", str(ex), warnings=warnings)
    except Exception as ex:
        return error("deploy_exception", f"{type(ex).__name__}: {ex}",
                     warnings=warnings)
    return ok(warnings=warnings, build_dir=build_dir, game_dir=gdir)


def undeploy(keep_mod: bool = False, game_dir: str | None = None) -> dict:
    from d2r_mod.build import DEFAULT_GAME_DIR as _DEFAULT
    from d2r_mod.deploy import undeploy_mod
    try:
        undeploy_mod(game_dir or _DEFAULT, keep_mod=keep_mod)
    except Exception as ex:
        return error("undeploy_exception", f"{type(ex).__name__}: {ex}")
    return ok(game_dir=game_dir or _DEFAULT, keep_mod=keep_mod)


def diff(file: str | None = None, summary: bool = False) -> dict:
    """Compare vanilla vs build tables. Returns list of changed files."""
    from d2r_mod.tsv import read_tsv_file
    from d2r_mod.diff import diff_tables, summarize_diff, format_diff
    root = _project_root()
    vanilla_dir = os.path.join(root, "vanilla")
    build_dir = os.path.join(root, "build")
    if not (os.path.isdir(vanilla_dir) and os.path.isdir(build_dir)):
        return error(
            "build_required",
            "both vanilla/ and build/ must exist; run d2r_mod_build first",
        )
    changed = []
    for dirpath, _, filenames in os.walk(vanilla_dir):
        for fname in sorted(filenames):
            if not fname.endswith(".txt"):
                continue
            if file and file.lower() != fname.lower():
                continue
            v_path = os.path.join(dirpath, fname)
            b_path = os.path.join(build_dir, os.path.relpath(v_path, vanilla_dir))
            if not os.path.exists(b_path):
                continue
            changes = diff_tables(read_tsv_file(v_path), read_tsv_file(b_path))
            if not changes:
                continue
            entry = {"file": fname, "change_count": len(changes)}
            if summary:
                entry["summary"] = summarize_diff(fname, changes)
            else:
                entry["detail"] = format_diff(fname, changes)
            changed.append(entry)
    return ok(changed_files=changed, total_changed=len(changed))


def extract(game_dir: str | None = None) -> dict:
    from d2r_mod.build import DEFAULT_GAME_DIR as _DEFAULT
    from d2r_mod.casc import extract_vanilla, _parse_build_info
    from d2r_mod.version import write_vanilla_version
    from d2r_mod.regen import regen_all
    root = _project_root()
    output_dir = os.path.join(root, "vanilla")
    gdir = game_dir or _DEFAULT
    try:
        result = extract_vanilla(gdir, output_dir)
        build_key = _parse_build_info(gdir)
        write_vanilla_version(output_dir, build_key)
        regen_all(output_dir)
    except FileNotFoundError as ex:
        return error("missing_dir", str(ex))
    except Exception as ex:
        return error("extract_exception", f"{type(ex).__name__}: {ex}")
    return ok(extracted=len(result), output_dir=output_dir)


def clean() -> dict:
    import shutil
    root = _project_root()
    build_dir = os.path.join(root, "build")
    vanilla_dir = os.path.join(root, "vanilla")
    actions = []
    if os.path.isdir(vanilla_dir):
        from d2r_mod.regen import regen_all
        regen_all(vanilla_dir)
        actions.append("regenerated chargen data from vanilla/")
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
        actions.append(f"removed {build_dir}")
    return ok(actions=actions)


def update(warn_conflicts: bool = False, no_regen: bool = False,
           game_dir: str | None = None) -> dict:
    """Run the full extract+build+deploy recovery pipeline."""
    r = extract(game_dir=game_dir)
    if r["status"] != "ok":
        return r
    r = build(warn_conflicts=warn_conflicts, no_regen=no_regen,
              game_dir=game_dir)
    if r["status"] != "ok":
        return r
    return deploy(force=True, no_build=True, game_dir=game_dir)


def audit(skills: bool = False, items: bool = False, audit_all: bool = False,
          output_dir: str | None = None) -> dict:
    from d2r_mod.tsv import read_tsv_file
    from d2r_mod.audit import (
        audit_skills, audit_items,
        generate_skills_report, generate_items_report,
    )
    root = _project_root()
    vanilla_dir = os.path.join(root, "vanilla")
    excel_dir = os.path.join(vanilla_dir, "data", "global", "excel")
    if not os.path.isdir(excel_dir):
        return error(
            "missing_dir",
            f"vanilla/ not extracted; expected {excel_dir}",
        )
    out = output_dir or os.path.join(root, "docs", "audit")
    os.makedirs(out, exist_ok=True)
    tables = {}
    for fname in os.listdir(excel_dir):
        if fname.endswith(".txt"):
            tables[f"data/global/excel/{fname}"] = read_tsv_file(
                os.path.join(excel_dir, fname)
            )
    reports = {}
    if skills or audit_all:
        results = audit_skills(tables)
        path = os.path.join(out, "skills_report.md")
        with open(path, "w") as f:
            f.write(generate_skills_report(results))
        reports["skills"] = {
            "report_path": path,
            "total": len(results),
            "flagged": sum(1 for r in results if r["flagged"]),
        }
    if items or audit_all:
        results = audit_items(tables)
        path = os.path.join(out, "items_report.md")
        with open(path, "w") as f:
            f.write(generate_items_report(results))
        reports["items"] = {
            "report_path": path,
            "total": len(results),
            "flagged": sum(1 for r in results if r["flagged"]),
        }
    return ok(reports=reports)
