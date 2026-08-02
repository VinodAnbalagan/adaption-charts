"""Probe the installed adaption SDK surface.

The public docs describe client.training_jobs and client.autoscientist, but
the installed SDK version may differ. This prints what's actually available
so 06_train.py can be corrected to match.

Usage:
    python pipeline/_sdk_probe.py
"""

from __future__ import annotations
import os
import sys


def main() -> None:
    try:
        import adaption
    except ImportError:
        sys.exit("adaption SDK not installed. Run: pip install 'adaption>=0.6.0'")

    print(f"adaption version: {getattr(adaption, '__version__', 'unknown')}")

    key = os.environ.get("ADAPTION_API_KEY")
    if not key:
        sys.exit("ADAPTION_API_KEY not set")

    from adaption import Adaption
    client = Adaption(api_key=key)

    print("\n--- top-level client attributes ---")
    resources = [
        a for a in dir(client)
        if not a.startswith("_") and not callable(getattr(client, a, None))
    ]
    for a in sorted(resources):
        print(f"  {a}")

    print("\n--- methods per resource ---")
    for a in sorted(resources):
        obj = getattr(client, a, None)
        if obj is None:
            continue
        methods = [
            m for m in dir(obj)
            if not m.startswith("_") and callable(getattr(obj, m, None))
        ]
        if methods:
            print(f"\n  {a}:")
            for m in sorted(methods):
                print(f"    .{m}()")

    # Try listing available training models — tells us valid --model ids
    print("\n--- training_models.list() ---")
    try:
        models = client.training_models.list()
        for m in models:
            # Print whatever fields exist
            if hasattr(m, "__dict__"):
                d = {k: v for k, v in vars(m).items() if not k.startswith("_")}
            elif isinstance(m, dict):
                d = m
            else:
                d = {"repr": repr(m)}
            print(f"  {d}")
    except Exception as e:
        print(f"  failed: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
