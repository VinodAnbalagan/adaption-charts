"""List recent AutoScientist runs for a dataset, newest first.

Dumps every field on the newest run (including column_mapping and any
error), then a one-line summary for the rest.

Usage:
    python pipeline/_runs.py --dataset-id <id>
    python pipeline/_runs.py --dataset-id <id> --limit 20
"""

from __future__ import annotations
import argparse
import os
import sys


def _fields(obj) -> dict:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
    return {"repr": repr(obj)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-id", required=True)
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    key = os.environ.get("ADAPTION_API_KEY")
    if not key:
        sys.exit("ADAPTION_API_KEY not set")

    from adaption import Adaption
    client = Adaption(api_key=key)

    runs = list(client.autoscientist.list(
        dataset_id=args.dataset_id, limit=args.limit,
    ))
    if not runs:
        print("no runs found")
        return

    newest = runs[0]
    print(f"=== newest run: {newest.id} ===")
    for k, v in _fields(newest).items():
        line = f"  {k}: {v}"
        print(line[:400])

    if len(runs) > 1:
        print(f"\n=== {len(runs) - 1} older runs ===")
        for r in runs[1:]:
            f = _fields(r)
            status = f.get("status", "?")
            model = f.get("model", "?")
            wr = f.get("best_win_rate")
            wr_s = f"  win_rate={wr}" if wr is not None else ""
            print(f"  {r.id}  {status:10s}  {model}{wr_s}")
            err = f.get("error")
            if err:
                print(f"      error: {str(err)[:200]}")


if __name__ == "__main__":
    main()
