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
    # NOTE: in adaption SDK 0.7.0 there is no client.training_jobs — the
    # single-run training resource was folded into client.autoscientist,
    # which carries recommend_hyperparams alongside create/get/list/etc.
    client = _client()
    kwargs = {"dataset_id": args.dataset_id}
    if args.model:
        # Accept VLM_MODELS shorthand (4b / 27b / 31b / scout) or a full id
        kwargs["model"] = VLM_MODELS.get(args.model, args.model)
        print(f"model: {kwargs['model']}")
    rec = client.autoscientist.recommend_hyperparams(**kwargs)
    print("recommended hyperparams (free — nothing started):")
    hp = getattr(rec, "hyperparams", None)
    if hp is None and isinstance(rec, dict):
        hp = rec.get("hyperparams")
    if hp is None:
        # Fall back to dumping whatever came back
        print(f"  {rec!r}")
        return
    items = hp.items() if isinstance(hp, dict) else vars(hp).items()
    for k, v in items:
        print(f"  {k}: {v}")


def cmd_models(args: argparse.Namespace) -> None:
    """List available base models, flagging the VLM (multimodal) ones.

    Our dataset is multimodal (chart images), so only VLM bases are valid.
    """
    client = _client()
    resp = client.training_models.list()
    models = getattr(resp, "models", None) or resp
    if isinstance(models, tuple):
        models = models[1]
    print(f"{'VLM':<5} {'size':<8} {'id'}")
    print("-" * 70)
    for m in models:
        mid = getattr(m, "id", None) or m.get("id")
        size = getattr(m, "model_size", None) or m.get("model_size", "?")
        is_vlm = "VLM" in mid or "Scout" in mid
        flag = " *" if is_vlm else ""
        print(f"{flag:<5} {size:<8} {mid}")
    print("\n* = vision-language model (required for this dataset)")


# ---------- train: launch autoscientist with column_mapping variant -------

# Available VLM base models (adaption SDK 0.7.0, training_models.list()).
# Our dataset is multimodal, so ONLY these are valid:
#
#   google/gemma-3-4b-it-VLM      4B    smallest VLM — most headroom
#   google/gemma-3-27b-it-VLM     27B   Run 1 base: 30 -> 70 (best result)
#   google/gemma-4-31B-it-VLM     31B   Run 3 base: 88 -> 12 (worst result)
#   meta-llama/Llama-4-Scout-...  109B  untested
#
# Headroom thesis (validated across runs 1-3): win rate scales INVERSELY
# with how good the base already is at the task. Run 3's 31B started at 88
# — almost no room to improve — and inverted. Run 1's 27B started at 30 and
# climbed to 70. The 4B VLM should have the most headroom of all.
VLM_MODELS = {
    "4b": "google/gemma-3-4b-it-VLM",
    "27b": "google/gemma-3-27b-it-VLM",
    "31b": "google/gemma-4-31B-it-VLM",
    "scout": "meta-llama/Llama-4-Scout-17B-16E-Instruct",
}


# ADAPTED dataset schema, confirmed by `columns` (NOT the source schema):
#   question, answer, enhanced_prompt, enhanced_completion, chart_type,
#   difficulty, id, notes, original_image, source, split, task_type, verified
#
# Gotchas learned the hard way:
#   - `inspect` shows configured_column_mapping, which points at the SOURCE
#     columns (image='file_name'). The adapted output renames it to
#     'original_image'. Always confirm with `columns` before training.
#   - The API's validation error can name the wrong column: it reported
#     "Selected column 'question' ... is not in this dataset" when the real
#     problem was the image column.
#   - Images are stored as URLs into the source HF repo, so that repo must
#     stay PUBLIC for the duration of training, not just ingestion.
VARIANT_MAPPINGS = {
    # Variant AUTO = omit column_mapping entirely; the platform infers from
    # the dataset's own configured mapping. Per the docs: "Omit it and the
    # platform infers."
    #
    # This is the RECOMMENDED default. Explicit mappings were rejected three
    # times with errors that named the prompt column even when that column
    # demonstrably existed in the adapted CSV header — the API's validation
    # message is unreliable, so don't fight it.
    "auto": None,

    # Variant A = Run 4 plan: original columns, bypass enhancement.
    "a": {
        "prompt": "question",
        "completion": "answer",
        "image": "original_image",
    },

    # Variant B = Ali plan: train on the adapted enhanced columns.
    "b": {
        "prompt": "enhanced_prompt",
        "completion": "enhanced_completion",
        "image": "original_image",
    },
}


def cmd_train(args: argparse.Namespace) -> None:
    client = _client()
    mapping = VARIANT_MAPPINGS[args.variant]
    # Allow shorthand model ids (4b / 27b / 31b / scout)
    model = VLM_MODELS.get(args.model, args.model) if args.model else None

    print(f"launching autoscientist variant '{args.variant}'")
    print(f"  column_mapping: {mapping if mapping else '(omitted — platform infers)'}")
    print(f"  max_iterations: {args.max_iterations}")
    print(f"  target_win_rate: {args.target_win_rate}")
    print(f"  model: {model or '(platform picks)'}")

    kwargs = {
        "dataset_id": args.dataset_id,
        "max_iterations": args.max_iterations,
        "target_win_rate": args.target_win_rate,
        "idempotency_key": (
            f"variant-{args.variant}-{model or 'auto'}-{args.dataset_id}"
            f"-{args.attempt}"
        ),
    }
    # mapping is None for variant 'auto' — omit the key entirely so the
    # platform infers from the dataset's configured mapping.
    if mapping is not None:
        kwargs["column_mapping"] = mapping
    if model:
        kwargs["model"] = model

    run = client.autoscientist.create(**kwargs)
    run_id = getattr(run, "id", None) or run["id"]
    status = getattr(run, "status", None) or run.get("status")
    print(f"\nRUN_ID: {run_id}   status: {status}")
    print("\nnext:")
    print(f"  python pipeline/06_train.py wait-train --run-id {run_id}")


def _dump_run(run) -> None:
    """Print every field on an AutoscientistRun object."""
    if hasattr(run, "model_dump"):          # pydantic v2
        fields = run.model_dump()
    elif hasattr(run, "dict"):              # pydantic v1
        fields = run.dict()
    elif hasattr(run, "__dict__"):
        fields = {k: v for k, v in vars(run).items() if not k.startswith("_")}
    else:
        fields = {"repr": repr(run)}
    for k, v in fields.items():
        print(f"  {k}: {v!r}"[:400])


def cmd_wait_train(args: argparse.Namespace) -> None:
    client = _client()
    print(f"waiting on run {args.run_id} (timeout {args.timeout}s)...")
    try:
        run = client.autoscientist.wait_for_completion(args.run_id, timeout=args.timeout)
    except Exception as e:
        print(f"wait raised: {type(e).__name__}: {e}")
        print("fetching current run state...")
        run = client.autoscientist.get(args.run_id)
    _dump_run(run)


def cmd_columns(args: argparse.Namespace) -> None:
    """Download the adapted dataset and print its actual column names.

    `inspect` shows configured_column_mapping — that's the mapping used
    DURING adaptation, pointing at the SOURCE columns. The adapted output
    has its own schema (original_prompt / enhanced_prompt / etc). Training
    column_mapping is validated against THAT schema, so we need the real
    header before launching a run.
    """
    import csv as _csv
    import io
    import urllib.request

    client = _client()
    dl = client.datasets.download(args.dataset_id)
    url = getattr(dl, "url", None) or getattr(dl, "download_url", None)
    if url is None and isinstance(dl, dict):
        url = dl.get("url") or dl.get("download_url")
    if url is None:
        print("could not find a download URL on the response; raw object:")
        _dump_run(dl)
        return

    print(f"fetching adapted dataset header...")
    with urllib.request.urlopen(url) as resp:
        # Read enough for the header plus one sample row
        chunk = resp.read(200_000).decode("utf-8", errors="replace")

    reader = _csv.reader(io.StringIO(chunk))
    header = next(reader, [])
    print(f"\nadapted dataset columns ({len(header)}):")
    for c in header:
        print(f"  {c}")

    row = next(reader, None)
    if row:
        print("\nfirst row (truncated):")
        for c, v in zip(header, row):
            print(f"  {c}: {v[:120]!r}")


def cmd_status(args: argparse.Namespace) -> None:
    """One-shot status check — dumps all fields including any error."""
    client = _client()
    run = client.autoscientist.get(args.run_id)
    _dump_run(run)


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

    sp = sub.add_parser("models")
    sp.set_defaults(func=cmd_models)

    sp = sub.add_parser("train")
    sp.add_argument("--dataset-id", required=True)
    sp.add_argument("--variant", choices=["auto", "a", "b"], default="auto")
    sp.add_argument("--max-iterations", type=int, default=3)
    sp.add_argument("--target-win-rate", type=float, default=0.75)
    sp.add_argument(
        "--model", default=None,
        help="Full model id, or a VLM_MODELS shorthand: 4b / 27b / 31b / scout",
    )
    sp.add_argument(
        "--attempt", default="1",
        help="Bump to force a new idempotency key when retrying a failed run",
    )
    sp.set_defaults(func=cmd_train)

    sp = sub.add_parser("wait-train")
    sp.add_argument("--run-id", required=True)
    sp.add_argument("--timeout", type=int, default=14400)
    sp.set_defaults(func=cmd_wait_train)

    sp = sub.add_parser("status")
    sp.add_argument("--run-id", required=True)
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("columns")
    sp.add_argument("--dataset-id", required=True)
    sp.set_defaults(func=cmd_columns)

    sp = sub.add_parser("download")
    sp.add_argument("--run-id", required=True)
    sp.add_argument("--out", default="best-checkpoint.tgz")
    sp.set_defaults(func=cmd_download)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
