"""Publish gold dataset to a private HuggingFace repo.

Stages a clean, upload-friendly layout in a temp dir, then pushes it as a
single upload. Repo defaults to PRIVATE (competitors won't be able to
download it during the challenge). Change with --public when ready.

Uploads (HF imagefolder layout — required for the platform to resolve
image paths on ingest):
  README.md           dataset card (from gold/README.md)
  metadata.csv        manifest with file_name column pointing at images/*
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

# Columns in the exported metadata.csv. HF imagefolder convention requires
# a 'file_name' column that points at images relative to the metadata.csv's
# directory. We keep the rest of the schema alongside as extra metadata.
EXPORT_COLS = [
    "file_name",       # HF imagefolder convention (was 'image_path')
    "id", "source", "question", "answer",
    "chart_type", "task_type", "difficulty", "verified", "split", "notes",
]


def _md_table(counter, label: str, total: int | None = None) -> str:
    """Render a Counter as a markdown table sorted by count desc."""
    lines = [f"| {label} | rows |" + (" share |" if total else ""),
             "|---|---:|" + ("---:|" if total else "")]
    for k, v in sorted(counter.items(), key=lambda x: -x[1]):
        share = f" {v / total * 100:.1f}% |" if total else ""
        lines.append(f"| {k} | {v} |{share}")
    return "\n".join(lines)


def _render_composition(rows: list[dict]) -> str:
    """Build the Composition section from live manifest data."""
    from collections import Counter
    n = len(rows)
    src = Counter(r["source"] for r in rows)
    ct = Counter(r["chart_type"] for r in rows)
    tt = Counter(r["task_type"] for r in rows)
    df = Counter(r["difficulty"] for r in rows)
    return "\n\n".join([
        "**By source**\n\n" + _md_table(src, "source", n),
        "**By chart_type**\n\n" + _md_table(ct, "chart_type"),
        "**By task_type**\n\n" + _md_table(tt, "task_type"),
        "**By difficulty**\n\n" + _md_table(df, "difficulty"),
    ])


def _sync_card(card_text: str, rows: list[dict]) -> str:
    """Replace the auto-generated regions of the dataset card.

    Uses HTML-comment markers so the hand-written prose stays untouched:
      <!-- AUTOGEN:counts -->   ... <!-- /AUTOGEN:counts -->
      <!-- AUTOGEN:composition --> ... <!-- /AUTOGEN:composition -->
    Falls back to leaving the card as-is if markers are missing.
    """
    import re
    from collections import Counter
    n = len(rows)
    src = Counter(r["source"] for r in rows)
    counts_block = (
        f"- **{n} rows total** — "
        + " + ".join(f"{v} {k}" for k, v in sorted(src.items(), key=lambda x: -x[1]))
    )

    def sub_region(text, name, replacement):
        pat = re.compile(
            rf"(<!-- AUTOGEN:{name} -->)(.*?)(<!-- /AUTOGEN:{name} -->)",
            re.DOTALL,
        )
        if not pat.search(text):
            return text
        return pat.sub(rf"\1\n{replacement}\n\3", text)

    text = sub_region(card_text, "counts", counts_block)
    text = sub_region(text, "composition", _render_composition(rows))
    return text


def stage(tmp: Path) -> tuple[int, int]:
    """Copy README, rewrite manifest paths, copy images. Returns (rows, images)."""
    if not MANIFEST.exists():
        sys.exit(f"manifest not found: {MANIFEST} — run 01/03/04 first")
    if not CARD.exists():
        sys.exit(f"dataset card not found: {CARD}")

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
        # HF imagefolder convention: file_name is relative to the
        # metadata.csv's directory.
        r["file_name"] = f"images/{fname}"

    metadata_csv = tmp / "metadata.csv"
    with metadata_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=EXPORT_COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # Dataset card: sync auto-generated count/composition regions from the
    # live manifest so it can never go stale, then write both to the staging
    # dir and back to gold/README.md so git tracks the current numbers.
    synced = _sync_card(CARD.read_text(), rows)
    (tmp / "README.md").write_text(synced)
    CARD.write_text(synced)

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
            commit_message="upload adaption-charts-p2-gold (imagefolder layout)",
            # Remove the previous non-imagefolder layout from the repo
            # so HF and Adaption see a clean imagefolder dataset.
            delete_patterns=["train.csv"],
        )
        print(f"\ndone. https://huggingface.co/datasets/{repo_id}")


if __name__ == "__main__":
    main()
