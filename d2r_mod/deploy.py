"""Deploy/undeploy mod files to D2R game directory."""

import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone


MOD_NAME = "rebalance"

_VDF_DIR = os.path.expanduser("~/.local/share/Steam/userdata")
_D2R_APP_ID = "2536520"
_BASE_LAUNCH_OPTS = "%command% -mod rebalance -txt"

# Paths for LD_PRELOAD runtime patcher
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LIBPATCH_SO = os.path.join(_PROJECT_ROOT, "d2r_mod", "host", "lib", "libpatch.so")
_LAUNCH_WRAPPER = os.path.join(_PROJECT_ROOT, "d2r_mod", "host", "lib", "launch_wrapper.sh")
_PATCHES_DIR = os.path.join(_PROJECT_ROOT, "d2r_mod", "host", "patches")
_ANALYSIS_DIR = os.path.join(_PROJECT_ROOT, "analysis", "runtime")


def _is_steam_running():
    """Check if the main Steam client process is running."""
    try:
        result = subprocess.run(
            ["pgrep", "-x", "steam"], capture_output=True, text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def _shutdown_steam():
    """Cleanly shut down Steam and wait for it to exit."""
    import time
    # steam -shutdown sends a clean shutdown signal
    subprocess.Popen(
        ["steam", "-shutdown"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    # Wait up to 15 seconds for Steam to exit
    for _ in range(30):
        time.sleep(0.5)
        if not _is_steam_running():
            print("Steam shut down.")
            time.sleep(1)  # extra wait for VDF flush
            return
    print("Warning: Steam did not shut down in 15s — VDF edit may be overwritten")


def _restart_steam():
    """Restart Steam in the background."""
    subprocess.Popen(
        ["steam"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    print("Steam restarting...")


def _build_launch_options(game_dir: str) -> str:
    """Build Steam launch options, adding wrapper script if libpatch.so exists.

    Uses a wrapper script instead of raw LD_PRELOAD env vars because
    Steam/pressure-vessel strips LD_PRELOAD from launch options before
    passing to the Proton runtime. The wrapper script sets LD_PRELOAD
    and D2R_PATCH_CONFIG, then execs the Proton command chain.
    """
    if not os.path.isfile(_LIBPATCH_SO):
        return _BASE_LAUNCH_OPTS
    return f'{_LAUNCH_WRAPPER} {_BASE_LAUNCH_OPTS}'


def _find_localconfig():
    """Find localconfig.vdf for the active Steam user."""
    matches = glob.glob(os.path.join(_VDF_DIR, "*/config/localconfig.vdf"))
    if not matches:
        return None
    return max(matches, key=os.path.getmtime)


def _set_launch_options(app_id, options):
    """Set or clear LaunchOptions for a Steam app in localconfig.vdf.

    WARNING: Steam caches localconfig.vdf in memory.  Editing the file while
    Steam is running will be silently overwritten on Steam's next auto-save.
    Callers must shut down Steam before calling this function.
    """
    if _is_steam_running():
        print("ERROR: Steam is running — VDF edits will be overwritten. "
              "Shut down Steam first.")
        return False

    path = _find_localconfig()
    if not path:
        print("Warning: localconfig.vdf not found — set launch options manually")
        return False

    shutil.copy2(path, path + ".bak")

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    in_app = False
    app_indent = ""
    insert_idx = None
    existing_idx = None
    brace_depth = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == f'"{app_id}"' and not in_app and insert_idx is None:
            in_app = True
            continue
        if in_app and stripped == "{" and brace_depth == 0:
            app_indent = line[:len(line) - len(line.lstrip())]
            brace_depth = 1
            insert_idx = i + 1
            continue
        if in_app and brace_depth > 0:
            if stripped == "{":
                brace_depth += 1
            elif stripped == "}":
                brace_depth -= 1
                if brace_depth == 0:
                    break  # found and parsed the first matching block
            elif brace_depth == 1 and stripped.startswith('"LaunchOptions"'):
                existing_idx = i

    if insert_idx is None:
        print(f"Warning: app {app_id} not found in localconfig.vdf")
        return False

    if options:
        new_line = f'{app_indent}\t"LaunchOptions"\t\t"{options}"\n'
        if existing_idx is not None:
            lines[existing_idx] = new_line
        else:
            lines.insert(insert_idx, new_line)
    else:
        if existing_idx is not None:
            del lines[existing_idx]

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return True

def _strip_patch_config(game_dir: str) -> None:
    """Remove patch-* lines from the CASC build config.

    D2R's TACT system tries to load the patch-config referenced in the build
    config from the CDN (tempest.corp.blizzard.net).  When the CDN is
    unreachable and the file isn't cached locally, TACT fails with
    "Failed to initialize data (corrupted?)" — Error Code 1.

    The patch-config is only used for delta patching and is not needed to run
    the game from a full installation.  Stripping it lets TACT init succeed
    offline.
    """
    build_info = os.path.join(game_dir, ".build.info")
    if not os.path.isfile(build_info):
        return
    with open(build_info, "r", encoding="utf-8") as f:
        lines = f.read().strip().split("\n")
    if len(lines) < 2:
        return
    headers = [h.split("!")[0].strip() for h in lines[0].split("|")]
    values = [v.strip() for v in lines[1].split("|")]
    try:
        idx = headers.index("Build Key")
        build_key = values[idx]
    except (ValueError, IndexError):
        return
    config_path = os.path.join(
        game_dir, "data", "config",
        build_key[:2], build_key[2:4], build_key,
    )
    if not os.path.isfile(config_path):
        return
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()
    if "patch-config" not in content:
        return
    # Check that the referenced patch-config file is actually missing
    m = re.search(r"^patch-config\s*=\s*(\S+)", content, re.MULTILINE)
    if m:
        pk = m.group(1)
        patch_path = os.path.join(
            game_dir, "data", "config", pk[:2], pk[2:4], pk,
        )
        if os.path.isfile(patch_path):
            return  # file exists, no need to strip
    original = config_path + ".original"
    if not os.path.isfile(original):
        shutil.copy2(config_path, original)
    cleaned = re.sub(r"^patch-(?:index|index-size|config|size|)\s*=.*\n?",
                     "", content, flags=re.MULTILINE)
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(cleaned)
    print("Stripped patch-config from CASC build config (offline TACT fix)")


from d2r_mod.build import DEFAULT_GAME_DIR


def _mod_root(game_dir: str) -> str:
    return os.path.join(game_dir, "mods", MOD_NAME, f"{MOD_NAME}.mpq")


class StaleVanillaError(RuntimeError):
    """Raised when vanilla data doesn't match the installed game version."""
    pass


def deploy_mod(build_dir: str, game_dir: str = DEFAULT_GAME_DIR,
               force: bool = False, vanilla_dir: str | None = None) -> None:
    if not os.path.isdir(build_dir):
        raise FileNotFoundError(f"build/ not found at {build_dir}")
    if not os.path.exists(os.path.join(game_dir, ".build.info")):
        print(f"WARNING: {game_dir} does not contain .build.info — may not be a D2R install")

    # Hard-fail on stale vanilla data unless --force
    if vanilla_dir is not None:
        from d2r_mod.version import check_stale
        stale_warning = check_stale(vanilla_dir, game_dir)
        if stale_warning and not force:
            raise StaleVanillaError(
                f"{stale_warning}\n"
                "Use --force to deploy anyway, or run 'd2r-mod update' to re-extract."
            )

    mod_root = _mod_root(game_dir)
    if os.path.exists(mod_root):
        shutil.rmtree(mod_root)

    shutil.copytree(build_dir, mod_root)
    print(f"Deployed to {mod_root}")

    _strip_patch_config(game_dir)

    # Set launch options FIRST — this is the critical step that enables the
    # mod.  patches.json is optional (only needed for runtime binary patching)
    # and must not block launch-option setup.
    launch_opts = _build_launch_options(game_dir)

    # Check if Steam is running — VDF edits get overwritten by Steam's
    # in-memory state on exit/auto-save. Must shut down Steam first.
    steam_running = _is_steam_running()
    if steam_running:
        print("Steam is running — shutting down to persist launch options...")
        _shutdown_steam()

    if _set_launch_options(_D2R_APP_ID, launch_opts):
        print(f"Steam launch options set to: {launch_opts}")
    else:
        print(f"Add to Steam launch options: {launch_opts}")

    # Generate patches.json for LD_PRELOAD runtime patcher (optional)
    try:
        _deploy_patches_json(game_dir)
    except Exception as e:
        print(f"Warning: patches.json generation failed ({e}) — "
              "binary patching disabled, mod data still active")

    if steam_running:
        _restart_steam()


def _deploy_patches_json(game_dir: str) -> None:
    """Generate patches.json and supporting files in game_dir."""
    from d2r_mod.host.config_gen import generate_patches_json, _sha256_file

    d2r_exe = os.path.join(game_dir, "D2R.exe")
    decrypted_pe = os.path.join(_ANALYSIS_DIR, "D2R_decrypted.exe")
    text_section = os.path.join(_ANALYSIS_DIR, "text_section.bin")
    guards_json = os.path.join(_ANALYSIS_DIR, "guards.json")
    output = os.path.join(game_dir, "patches.json")

    config = generate_patches_json(
        patches_dir=_PATCHES_DIR,
        d2r_exe_path=d2r_exe,
        decrypted_pe_path=decrypted_pe,
        text_section_path=text_section,
        guards_path=guards_json,
        output_path=output,
    )

    # Deploy manifest for traceability
    git_commit = ""
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_PROJECT_ROOT, stderr=subprocess.DEVNULL,
        ).decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    manifest = {
        "deployed_at": datetime.now(timezone.utc).isoformat(),
        "patches_json_sha256": _sha256_file(output) if os.path.isfile(output) else "",
        "libpatch_so_sha256": _sha256_file(_LIBPATCH_SO) if os.path.isfile(_LIBPATCH_SO) else "",
        "d2r_exe_sha256": config.get("binary_hash", ""),
        "git_commit": git_commit,
    }
    manifest_path = os.path.join(game_dir, "deploy_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    # Quick-disable script
    disable_path = os.path.join(game_dir, "disable_patches.sh")
    with open(disable_path, "w") as f:
        f.write("#!/bin/bash\n")
        f.write("# Remove LD_PRELOAD from Steam launch options to disable patching.\n")
        f.write(f'python3 -m d2r_mod undeploy --keep-mod\n')
    os.chmod(disable_path, 0o755)


def deploy_casc(build_dir: str, vanilla_dir: str,
                game_dir: str = DEFAULT_GAME_DIR) -> dict | None:
    """Inject modified JSON files into D2R's CASC archive.

    Compares JSON files in build_dir against vanilla_dir. Any file whose
    content differs is injected via the CASC writer. Files that are
    identical to vanilla are skipped.

    Returns inject_files() result dict, or None if no changes.
    """
    file_map = {}

    for dirpath, _, filenames in os.walk(build_dir):
        for fname in filenames:
            if not fname.endswith(".json") or fname == "modinfo.json":
                continue

            build_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(build_path, build_dir)
            vanilla_path = os.path.join(vanilla_dir, rel_path)

            # Only inject files that differ from vanilla
            if not os.path.exists(vanilla_path):
                continue  # new JSON files not in TVFS can't be injected

            with open(build_path, "rb") as f:
                build_content = f.read()
            with open(vanilla_path, "rb") as f:
                vanilla_content = f.read()

            if build_content == vanilla_content:
                continue

            # TVFS paths use forward slashes, lowercase
            vpath = rel_path.replace(os.sep, "/")
            file_map[vpath] = build_content

    if not file_map:
        print("No modified JSON files to inject into CASC.")
        return None

    from d2r_mod.casc_write import inject_files

    print(f"Injecting {len(file_map)} modified JSON file(s) into CASC...")
    for vpath in sorted(file_map):
        print(f"  {vpath} ({len(file_map[vpath])} bytes)")

    result = inject_files(game_dir, file_map)

    for item in result["injected"]:
        print(f"  Injected: {item['path']} (ekey={item['ekey'][:18]}...)")
    print(f"Created {len(result['idx_files'])} .idx file(s)")
    print(f"New Build Key: {result['new_build_key']}")

    return result


def undeploy_mod(game_dir: str = DEFAULT_GAME_DIR,
                 keep_mod: bool = False) -> None:
    if not keep_mod:
        mod_top = os.path.join(game_dir, "mods", MOD_NAME)
        if os.path.exists(mod_top):
            shutil.rmtree(mod_top)
            print(f"Removed {mod_top}")
        else:
            print(f"No mod found at {mod_top}")

    # Clean up runtime patcher artifacts
    for name in ("patches.json", "deploy_manifest.json",
                 "disable_patches.sh", "d2r_patch.log"):
        path = os.path.join(game_dir, name)
        if os.path.isfile(path):
            os.remove(path)
            print(f"Removed {path}")

    if _set_launch_options(_D2R_APP_ID, ""):
        print("Steam launch options cleared.")
        print("Restart Steam for changes to take effect.")
    else:
        print(f"Remember to clear Steam launch options")


_VERIFY_FILES = [
    "data/global/excel/Skills.txt",
    "data/global/excel/Missiles.txt",
    "data/global/excel/Hireling.txt",
    "data/global/excel/MonStats.txt",
    "data/global/excel/MonProp.txt",
]


def _file_md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def verify_deploy(build_dir: str, game_dir: str = DEFAULT_GAME_DIR) -> bool:
    """Compare key files between build/ and deployed mod. Returns True if all match."""
    mod_root = _mod_root(game_dir)
    all_ok = True
    print("\nDeploy verification:")
    for rel in _VERIFY_FILES:
        build_path = os.path.join(build_dir, rel)
        deploy_path = os.path.join(mod_root, rel)
        if not os.path.isfile(build_path):
            continue
        if not os.path.isfile(deploy_path):
            print(f"  MISSING  {rel}")
            all_ok = False
            continue
        b_hash = _file_md5(build_path)
        d_hash = _file_md5(deploy_path)
        if b_hash == d_hash:
            print(f"  OK       {rel}  [{b_hash}]")
        else:
            print(f"  MISMATCH {rel}  build={b_hash} deployed={d_hash}")
            all_ok = False
    if all_ok:
        print("All key files verified.")
    else:
        print("WARNING: deploy mismatch detected!")
    return all_ok
