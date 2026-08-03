"""Push MODEL_CARD.md and the dataset card to HuggingFace.

Adaption's "Publish to HuggingFace" uploads the weights but writes a
minimal auto-generated card. This overwrites that card with ours, and
optionally re-pushes the dataset card too.

Prereqs:
    huggingface-cli login    (or HF_TOKEN in env)

Usage:
    python pipeline/08_push_cards.py --model-repo vinod-anbalagan/gridline
    python pipeline/08_push_cards.py --model-repo vinod-anbalagan/gridline --dataset-too
    python pipeline/08_push_cards.py --model-repo ... --dry-run
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MODEL_CARD = REPO / "MODEL_CARD.md"
DATASET_CARD = REPO / "gold" / "README.md"

DEFAULT_DATASET_REPO = "vinod-anbalagan/adaption-charts-p2-gold"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-repo", required=True,
                    help="e.g. vinod-anbalagan/gridline")
    ap.add_argument("--dataset-repo", default=DEFAULT_DATASET_REPO)
    ap.add_argument("--dataset-too", action="store_true",
                    help="also re-push gold/README.md to the dataset repo")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not MODEL_CARD.is_file():
        sys.exit(f"missing {MODEL_CARD}")
    card = MODEL_CARD.read_text()
    print(f"MODEL_CARD.md: {len(card)} chars, {card.count(chr(10))} lines")

    if args.dataset_too:
        if not DATASET_CARD.is_file():
            sys.exit(f"missing {DATASET_CARD}")
        dcard = DATASET_CARD.read_text()
        print(f"gold/README.md: {len(dcard)} chars, {dcard.count(chr(10))} lines")

    if args.dry_run:
        print("\ndry-run — nothing pushed")
        print(f"  would write README.md -> {args.model_repo} (model)")
        if args.dataset_too:
            print(f"  would write README.md -> {args.dataset_repo} (dataset)")
        return

    from huggingface_hub import HfApi, whoami
    try:
        print(f"HF logged in as: {whoami()['name']}")
    except Exception as e:
        sys.exit(f"HF not logged in. Run: huggingface-cli login\n  {e}")

    api = HfApi()

    print(f"\npushing model card -> {args.model_repo}")
    api.upload_file(
        path_or_fileobj=str(MODEL_CARD),
        path_in_repo="README.md",
        repo_id=args.model_repo,
        repo_type="model",
        commit_message="add model card",
    )
    print(f"  https://huggingface.co/{args.model_repo}")

    if args.dataset_too:
        print(f"\npushing dataset card -> {args.dataset_repo}")
        api.upload_file(
            path_or_fileobj=str(DATASET_CARD),
            path_in_repo="README.md",
            repo_id=args.dataset_repo,
            repo_type="dataset",
            commit_message="add perceptual difficulty taxonomy",
        )
        print(f"  https://huggingface.co/datasets/{args.dataset_repo}")


if __name__ == "__main__":
    main()
