"""End-to-end AutoScientist training pipeline, modular subcommands.

Every step is a separate command so you can review before spending credits
on the next stage. Prints all IDs; you pass them into subsequent commands
(nothing is persisted to disk except the packed CSV and the checkpoint).

RECOMMENDED HYBRID FLOW (UI for dataset, API for training):
  In the web UI:
    - Import from Hugging Face -> vinod-anbalagan/adaption-charts-p2-gold
    - Column mapping: question -> prompt, answer -> completion, image -> image
    - Recipe toggles (ON: Prompt Rephrase, Metadata Injection;
                      OFF: Dedup, Reasoning traces, Hallucination mitigation,
                           House Special)
    - Trigger adaptation, watch View tab for quality spot-check
    - Note the DATASET_ID from the URL bar

  Then here via API:
    - inspect       : see adapted column names for variant B mapping
    - recommend     : free hyperparam suggestion for our data size
    - train         : autoscientist.create with variant a / b
    - wait-train    : poll the search loop
    - download      : stream best checkpoint

The pack / upload / adapt / wait-adapt subcommands are the FULL-API
alternative if you'd rather script the ingestion too. Not recommended
for a first submission — UI gives better visual control there.

Full flow (if not using UI):

    # 1. Pack the manifest + images into a bytes-embedded CSV (local, free)
    python pipeline/06_train.py pack --out /tmp/adapt_upload.csv

    # 2. Upload the CSV to Adaption. Prints dataset_id.
    python pipeline/06_train.py upload --csv /tmp/adapt_upload.csv

    # 3. Kick off Adaptive Data adaptation with the Ali-config toggles
    #    (Prompt Rephrase ON, Metadata Injection ON, everything else OFF).
    #    NOTE: recipe toggles for Adaptive Data may need to be configured
    #    via the web UI before this call — see notes below. Prints run.
    python pipeline/06_train.py adapt --dataset-id <id>

    # 4. Wait for adaptation to complete
    python pipeline/06_train.py wait-adapt --dataset-id <id>

    # 5. Inspect the adapted schema (what enhanced columns now exist)
    python pipeline/06_train.py inspect --dataset-id <id>

    # 6. (Free) Get recommended hyperparameters for our dataset size
    python pipeline/06_train.py recommend --dataset-id <id>

    # 7. Launch autoscientist training with a column_mapping VARIANT.
    #    Variant A (Run 4 plan): original {question, answer} columns
    #    Variant B (Ali plan)  : enhanced {enhanced_prompt, enhanced_completion}
    python pipeline/06_train.py train --dataset-id <id> --variant a
    python pipeline/06_train.py train --dataset-id <id> --variant b

    # 8. Wait for autoscientist to converge
    python pipeline/06_train.py wait-train --run-id <run_id>

    # 9. Download best checkpoint (streams .tgz)
    python pipeline/06_train.py download --run-id <run_id> --out ckpt.tgz

Prereqs:
    pip install "adaption>=0.6.0"
    export ADAPTION_API_KEY=...

Notes on Adaptive Data recipe toggles:
    Our target config is the Ali variant refined for short-answer safety:
      - Prompt Rephrase           : ON
      - Prompt Deduplication      : OFF (image datasets — same prompt across
                                    different images is legit; dedup would
                                    kill valid rows)
      - Prompt Metadata Injection : ON
      - Reasoning traces          : OFF (would wrap short answers with
                                    'Reasoning:' prefix — killed Vinod's
                                    Run 2)
      - Hallucination mitigation  : OFF (killed Vinod's Run 3 via abstain
                                    on unannotated figures)
      - House Special             : OFF (risky for short-answer format;
                                    revisit after seeing the base run)
    The datasets.run() SDK signature exposed in the public guide only shows
    column_mapping. Recipe toggle names via API are TBD-until-first-run; if
    the SDK doesn't accept them yet, configure once in the web UI before
    calling adapt, and this script's --adapt step just triggers.
"""

from __future__ import annotations
import argparse
import base64
import csv
import mimetypes
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GOLD = REPO / "gold"
MANIFEST = GOLD / "manifest.csv"


# ---------- pack: build a bytes-embedded CSV for direct upload -------------

def cmd_pack(args: argparse.Namespace) -> None:
    """Build a CSV with images inlined as data URIs so the HF repo stays private."""
    if not MANIFEST.exists():
        sys.exit(f"manifest not found: {MANIFEST}")
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)

    with MANIFEST.open() as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit("manifest empty")

    # We include the metadata columns (chart_type, task_type, difficulty)
    # even though they're not mapped for training — they're kept as
    # unused metadata in the adapted dataset.
    out_cols = [
        "id", "question", "answer", "image",
        "chart_type", "task_type", "difficulty",
        "source", "verified", "split", "notes",
    ]

    n_missing = 0
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=out_cols)
        w.writeheader()
        for r in rows:
            img_abs = REPO / r["image_path"]
            if not img_abs.is_file():
                n_missing += 1
                continue
            mime, _ = mimetypes.guess_type(img_abs.name)
            mime = mime or "image/png"
            data = img_abs.read_bytes()
            b64 = base64.b64encode(data).decode("ascii")
            uri = f"data:{mime};base64,{b64}"
            row_out = {c: r.get(c, "") for c in out_cols}
            row_out["image"] = uri
            w.writerow(row_out)

    kept = len(rows) - n_missing
    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"packed {kept} rows into {out}")
    print(f"file size: {size_mb:.1f} MB")
    if n_missing:
        print(f"WARNING: skipped {n_missing} rows with missing image files")


# ---------- upload: push CSV to Adaption, print dataset_id -----------------

def _client():
    try:
        from adaption import Adaption
    except ImportError:
        sys.exit("adaption SDK not installed. Run: pip install 'adaption>=0.6.0'")
    key = os.environ.get("ADAPTION_API_KEY")
    if not key:
        sys.exit("ADAPTION_API_KEY not set")
    return Adaption(api_key=key)


def cmd_upload(args: argparse.Namespace) -> None:
    client = _client()
    csv_path = Path(args.csv).expanduser()
    if not csv_path.is_file():
        sys.exit(f"csv not found: {csv_path}")
    print(f"uploading {csv_path} ({csv_path.stat().st_size / 1024 / 1024:.1f} MB)...")
    result = client.datasets.upload_file(str(csv_path))
    dataset_id = getattr(result, "dataset_id", None) or result["dataset_id"]
    print(f"\nDATASET_ID: {dataset_id}")
    print("\nnext:")
    print(f"  python pipeline/06_train.py adapt --dataset-id {dataset_id}")


# ---------- adapt: run Adaptive Data on the uploaded dataset ---------------

def cmd_adapt(args: argparse.Namespace) -> None:
    client = _client()
    print(f"triggering adaptation on {args.dataset_id}...")
    # Column mapping: our schema has 'question' (prompt) + 'answer' (completion)
    # + 'image' (multimodal context, dedicated field per docs).
    mapping = {
        "prompt": "question",
        "completion": "answer",
        "image": "image",
    }
    print(f"column_mapping: {mapping}")
    # datasets.run signature per docs takes column_mapping. Recipe toggles
    # (rephrase/dedup/metadata/traces/hallucination/house_special) may be
    # passed as kwargs — SDK-version dependent. If it errors on unknown
    # kwarg, remove and set toggles via web UI before this step.
    try:
        client.datasets.run(
            args.dataset_id,
            column_mapping=mapping,
        )
        print("adaptation started. poll with:")
        print(f"  python pipeline/06_train.py wait-adapt --dataset-id {args.dataset_id}")
    except Exception as e:
        sys.exit(f"adapt call failed: {e}")


def cmd_wait_adapt(args: argparse.Namespace) -> None:
    client = _client()
    print(f"waiting on adaptation of {args.dataset_id}...")
    try:
        client.datasets.wait_for_completion(args.dataset_id, timeout=args.timeout)
        print("adaptation complete.")
    except Exception as e:
        sys.exit(f"wait failed: {e}")


# ---------- inspect: dump adapted schema so we know column names ----------

def cmd_inspect(args: argparse.Namespace) -> None:
    client = _client()
    ds = client.datasets.get(args.dataset_id)
    print("adapted dataset details:")
    for k, v in vars(ds).items() if hasattr(ds, "__dict__") else ds.items():
        print(f"  {k}: {v!r}"[:200])


# ---------- recommend: get suggested hyperparams (FREE) -------------------

def cmd_recommend(args: argparse.Namespace) -> None:
    client = _client()
    kwargs = {"dataset_id": args.dataset_id}
    if args.model:
        kwargs["model"] = args.model
    rec = client.training_jobs.recommend_hyperparams(**kwargs)
    print("recommended hyperparams (free — nothing started):")
    hp = getattr(rec, "hyperparams", None) or rec.get("hyperparams")
    for k, v in (hp.items() if isinstance(hp, dict) else vars(hp).items()):
        print(f"  {k}: {v}")


# ---------- train: launch autoscientist with column_mapping variant -------

VARIANT_MAPPINGS = {
    # Variant A = Run 4 plan: original columns, bypass enhancement.
    # Fed original 'question' as prompt and original 'answer' as completion.
    "a": {"prompt": "question", "completion": "answer", "image": "image"},

    # Variant B = Ali plan: use adapted enhanced columns.
    # Adapted schema adds 'enhanced_prompt' and 'enhanced_completion'.
    # Column names may vary per adaptation run — confirm via `inspect`.
    "b": {"prompt": "enhanced_prompt", "completion": "enhanced_completion", "image": "image"},
}


def cmd_train(args: argparse.Namespace) -> None:
    client = _client()
    mapping = VARIANT_MAPPINGS[args.variant]
    print(f"launching autoscientist variant '{args.variant}'")
    print(f"  column_mapping: {mapping}")
    print(f"  max_iterations: {args.max_iterations}")
    print(f"  target_win_rate: {args.target_win_rate}")

    kwargs = {
        "dataset_id": args.dataset_id,
        "max_iterations": args.max_iterations,
        "target_win_rate": args.target_win_rate,
        "column_mapping": mapping,
        "idempotency_key": f"variant-{args.variant}-{args.dataset_id}",
    }
    if args.model:
        kwargs["model"] = args.model

    run = client.autoscientist.create(**kwargs)
    run_id = getattr(run, "id", None) or run["id"]
    status = getattr(run, "status", None) or run.get("status")
    print(f"\nRUN_ID: {run_id}   status: {status}")
    print("\nnext:")
    print(f"  python pipeline/06_train.py wait-train --run-id {run_id}")


def cmd_wait_train(args: argparse.Namespace) -> None:
    client = _client()
    print(f"waiting on run {args.run_id} (default timeout 4h)...")
    try:
        run = client.autoscientist.wait_for_completion(args.run_id, timeout=args.timeout)
        print(f"status: {getattr(run, 'status', None) or run['status']}")
        print(f"best_win_rate: {getattr(run, 'best_win_rate', None) or run.get('best_win_rate')}")
        print(f"iterations_completed: {getattr(run, 'iterations_completed', None) or run.get('iterations_completed')}")
    except Exception as e:
        sys.exit(f"wait failed: {e}")


# ---------- download: pull best checkpoint --------------------------------

def cmd_download(args: argparse.Namespace) -> None:
    client = _client()
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"streaming best checkpoint of {args.run_id} to {out}...")
    with client.autoscientist.with_streaming_response.download(args.run_id) as response:
        response.stream_to_file(str(out))
    print(f"done: {out} ({out.stat().st_size / 1024 / 1024:.1f} MB)")
    print("extract with: tar xf " + str(out))


# ---------- CLI --------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("pack")
    sp.add_argument("--out", default="/tmp/adapt_upload.csv")
    sp.set_defaults(func=cmd_pack)

    sp = sub.add_parser("upload")
    sp.add_argument("--csv", required=True)
    sp.set_defaults(func=cmd_upload)

    sp = sub.add_parser("adapt")
    sp.add_argument("--dataset-id", required=True)
    sp.set_defaults(func=cmd_adapt)

    sp = sub.add_parser("wait-adapt")
    sp.add_argument("--dataset-id", required=True)
    sp.add_argument("--timeout", type=int, default=3600)
    sp.set_defaults(func=cmd_wait_adapt)

    sp = sub.add_parser("inspect")
    sp.add_argument("--dataset-id", required=True)
    sp.set_defaults(func=cmd_inspect)

    sp = sub.add_parser("recommend")
    sp.add_argument("--dataset-id", required=True)
    sp.add_argument("--model", default=None)
    sp.set_defaults(func=cmd_recommend)

    sp = sub.add_parser("train")
    sp.add_argument("--dataset-id", required=True)
    sp.add_argument("--variant", choices=["a", "b"], required=True)
    sp.add_argument("--max-iterations", type=int, default=3)
    sp.add_argument("--target-win-rate", type=float, default=0.75)
    sp.add_argument("--model", default=None)
    sp.set_defaults(func=cmd_train)

    sp = sub.add_parser("wait-train")
    sp.add_argument("--run-id", required=True)
    sp.add_argument("--timeout", type=int, default=14400)
    sp.set_defaults(func=cmd_wait_train)

    sp = sub.add_parser("download")
    sp.add_argument("--run-id", required=True)
    sp.add_argument("--out", default="best-checkpoint.tgz")
    sp.set_defaults(func=cmd_download)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
