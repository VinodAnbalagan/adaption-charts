"""Check whether training_models.list() exposes modality anywhere.

The repr of a Model object may omit None-valued fields, so a `modalities`
or `supports_vision` field could exist without showing up. This dumps the
full schema and every value, including Nones.

Usage:
    python pipeline/_model_fields.py
"""

from __future__ import annotations
import os
import sys


def main() -> None:
    key = os.environ.get("ADAPTION_API_KEY")
    if not key:
        sys.exit("ADAPTION_API_KEY not set")

    from adaption import Adaption
    client = Adaption(api_key=key)

    resp = client.training_models.list()
    models = getattr(resp, "models", None) or resp
    if isinstance(models, tuple):
        models = models[1]
    models = list(models)
    m = models[0]

    print(f"model object type: {type(m)}")

    # 1. Declared schema — catches fields that are None and hidden from repr
    print("\n--- declared fields (pydantic schema) ---")
    fields = getattr(type(m), "model_fields", None)
    if fields:
        for name, info in fields.items():
            print(f"  {name}: {info.annotation}")
    else:
        print("  (no model_fields; not a pydantic v2 model)")

    # 2. Full dump including None values
    print("\n--- full dump of first model (incl. None) ---")
    if hasattr(m, "model_dump"):
        d = m.model_dump()
    elif hasattr(m, "dict"):
        d = m.dict()
    else:
        d = {k: v for k, v in vars(m).items() if not k.startswith("_")}
    for k, v in d.items():
        print(f"  {k}: {v!s}")

    # 3. Any extra fields the SDK stashed outside the schema
    extra = getattr(m, "model_extra", None)
    print(f"\n--- model_extra ---\n  {extra}")

    # 4. Raw JSON as returned by the API, before SDK parsing
    print("\n--- raw API response (first model) ---")
    try:
        raw = client.training_models.with_raw_response.list()
        import json
        payload = json.loads(raw.text)
        first = payload.get("models", payload)
        if isinstance(first, list) and first:
            for k, v in first[0].items():
                print(f"  {k}: {v!s}")
        else:
            print(f"  {str(payload)[:600]}")
    except Exception as e:
        print(f"  could not fetch raw response: {type(e).__name__}: {e}")

    # 5. Scan every model for anything modality-shaped
    print("\n--- scan: any field name hinting at modality? ---")
    hints = ("modal", "vision", "image", "vlm", "multimodal", "input_type",
             "capabilit", "supports")
    found = set()
    for mm in models:
        dd = mm.model_dump() if hasattr(mm, "model_dump") else vars(mm)
        for k in dd:
            if any(h in k.lower() for h in hints):
                found.add(k)
    print(f"  {sorted(found) if found else 'none found'}")

    # 6. What the id/display_name alone would tell you
    print("\n--- id vs display_name for known-multimodal models ---")
    for mm in models:
        mid = getattr(mm, "id", "")
        if any(s in mid for s in ("VLM", "Qwen3.5", "Scout")):
            print(f"  {mid}  |  {getattr(mm, 'display_name', '')}")


if __name__ == "__main__":
    main()
