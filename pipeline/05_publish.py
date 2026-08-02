"""Publish gold dataset to a private HuggingFace repo.

Stages a clean, upload-friendly layout in a temp dir, then pushes it as a
single upload. Repo defaults to PRIVATE (competitors won't be able to
download it during the challenge). Change with --public when ready.

Uploads:
  README.md           dataset card (from gold/README.md)
  train.csv           full manifest with columns AutoScientist needs
  images/*.png        all chart images referenced by the manifest

Does NOT upload:
  gold/raw/            synthetic provenance (kept in git repo only)
  gold/hardset_raw/    original hardset screenshots (kept in git repo only)

Prereqs:
  1. `huggingface-cli login`  (or set HF_TOKEN env var)
  2. gold/manifest.csv verified by pipeline/04_verify.py

Usage:
  python pipeline/05_publish.py                            # private, default repo
  python pipeline/05_publish.py --repo-name my-dataset     # custom repo name
  python pipeline/05_publish.py --dry-run                  # stage locally, print, don't push
  python pipeline/05_publish.py --public                   # public visibility (careful)
"""

from __future__ import annotations
import argparse
import csv
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GOLD = REPO / "gold"
MANIFEST = GOLD / "manifest.csv"
IMAGES = GOLD / "images"
CARD = GOLD / "README.md"

DEFAULT_USER = "vinod-anbalagan"
DEFAULT_REPO_NAME = "adaption-charts-p2-gold"

# Columns kept in the exported train.csv. All original manifest columns,
# but 'image_path' will be rewritten from "gold/images/..." to "images/..."
# to match the HF-side folder layout.
EXPORT_COLS = [
    "id", "source", "image_path", "question", "answer",
    "chart_type", "task_type", "difficulty", "verified", "split", "notes",
]


def stage(tmp: Path) -> tuple[int, int]:
    """Copy README, rewrite manifest paths, copy images. Returns (rows, images)."""
    if not MANIFEST.exists():
        sys.exit(f"manifest not found: {MANIFEST} — run 01/03/04 first")
    if not CARD.exists():
        sys.exit(f"dataset card not found: {CARD}")

    shutil.copyfile(CARD, tmp / "README.md")

    stage_images = tmp / "images"
    stage_images.mkdir()

    with MANIFEST.open() as f:
        rows = list(csv.DictReader(f))

    copied: set[str] = set()
    for r in rows:
        src_rel = r["image_path"]
        fname = Path(src_rel).name
        if fname not in copied:
            src_abs = REPO / src_rel
            if not src_abs.is_file():
                sys.exit(f"missing image on disk: {src_abs}")
            shutil.copyfile(src_abs, stage_images / fname)
            copied.add(fname)
        r["image_path"] = f"images/{fname}"

    train_csv = tmp / "train.csv"
    with train_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=EXPORT_COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    return len(rows), len(copied)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-name", default=DEFAULT_REPO_NAME)
    ap.add_argument("--user", default=DEFAULT_USER)
    ap.add_argument("--public", action="store_true",
                    help="Make repo public (default: private)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Stage locally, print the layout, don't push")
    args = ap.parse_args()

    if not args.dry_run:
        # Import huggingface_hub lazily so --dry-run works without it
        from huggingface_hub import HfApi, whoami
        try:
            who = whoami()
            print(f"HF logged in as: {who['name']}")
        except Exception as e:
            sys.exit(f"HF not logged in. Run: huggingface-cli login\n  {e}")

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        n_rows, n_imgs = stage(tmp)
        print(f"staged: {n_rows} rows / {n_imgs} images")

        if args.dry_run:
            print("\nstaged layout:")
            for p in sorted(tmp.rglob("*")):
                if p.is_file():
                    size = p.stat().st_size
                    print(f"  {p.relative_to(tmp)!s:<40}  {size:>10} bytes")
            print("\ndry-run complete; nothing pushed")
            return

        from huggingface_hub import HfApi
        repo_id = f"{args.user}/{args.repo_name}"
        visibility = "PUBLIC" if args.public else "private"
        print(f"pushing to hf://datasets/{repo_id} ({visibility})...")

        api = HfApi()
        api.create_repo(
            repo_id=repo_id,
            repo_type="dataset",
            private=not args.public,
            exist_ok=True,
        )
        api.upload_folder(
            folder_path=str(tmp),
            repo_id=repo_id,
            repo_type="dataset",
            commit_message="upload adaption-charts-p2-gold (task 9)",
        )
        print(f"\ndone. https://huggingface.co/datasets/{repo_id}")


if __name__ == "__main__":
    main()
