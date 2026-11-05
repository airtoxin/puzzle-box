"""Export reviewed source files and locked runtime pins; never upload a worktree wholesale."""

import argparse
from pathlib import Path
import subprocess
import tomllib

from web_assets import ASSET_TYPES

ROOT = Path(__file__).resolve().parents[1]
MODULES = {"analyze_shading", "finite_shading", "generate_shading", "generate_slitherlink", "generate_yajilin",
           "shading_recipe", "edge_answers", "json_records", "web_answers", "web_catalog", "web_coupled",
           "web_loop", "web_server", "web_worker", "web_hosted", "web_assets"}
PACKAGES = ("puzzle", "puzzle-defs", "generator")
DEPENDENCIES = {"absl-py", "immutabledict", "numpy", "ortools", "pandas", "protobuf", "python-dateutil", "six", "typing-extensions"}


def files() -> dict[str, bytes]:
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True).stdout.decode().split("\0")
    result = {}
    for name in tracked:
        path = Path(name)
        if (name.startswith(tuple(f"packages/{p}/src/" for p in PACKAGES))
                and path.suffix == ".py" and not name.endswith("-test.py")):
            result[name] = (ROOT / path).read_bytes()
    for module in sorted(MODULES):
        name = f"examples/{module}.py"
        if name not in tracked: raise ValueError(f"Required source is not tracked: {name}")
        result[name] = (ROOT / name).read_bytes()
    for name in ASSET_TYPES:
        result[f"public/{name}"] = (ROOT / "apps/web" / name).read_bytes()
    for name in ("vercel.json", "api/index.py"):
        result[name] = (ROOT / "deploy/vercel" / name).read_bytes()
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    versions = {p["name"]: p["version"] for p in lock["package"] if p["name"] in DEPENDENCIES}
    if set(versions) != DEPENDENCIES: raise ValueError("Missing runtime dependencies in uv.lock")
    result["requirements.txt"] = ("# Runtime pins from uv.lock; Linux deployment.\n" +
                                  "".join(f"{name}=={versions[name]}\n" for name in sorted(versions))).encode()
    result[".python-version"] = b"3.12\n"
    return result


def export(destination: Path) -> dict[str, bytes]:
    payload = files()
    # Refuse an existing directory, including an empty one: no deletion, cleanup,
    # overwriting existing source, or symlink-following within an old artifact.
    destination.mkdir(parents=True, exist_ok=False)
    for name, data in payload.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    artifact = export(args.output)
    print(f"Exported {len(artifact)} files, {sum(map(len, artifact.values()))} source bytes to {args.output}")
