"""Copy only the public Web assets for a repository-root Vercel build."""

from pathlib import Path

from web_assets import ASSET_TYPES

ROOT = Path(__file__).resolve().parents[1]
ASSETS = tuple(ASSET_TYPES)


def build(destination: Path) -> None:
    if destination.is_symlink():
        raise ValueError("Static output must not be a symlink")
    destination.mkdir(parents=True, exist_ok=True)
    if any(path.name not in ASSETS or not path.is_file() or path.is_symlink()
           for path in destination.iterdir()):
        raise ValueError("Static output contains unexpected files")
    for name in ASSETS:
        (destination / name).write_bytes((ROOT / "apps" / "web" / name).read_bytes())


if __name__ == "__main__":
    build(ROOT / "build" / "vercel-public")
