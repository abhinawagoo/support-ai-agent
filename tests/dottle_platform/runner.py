"""CLI entry: run all Dottle scenarios (HTTP asserts + client smoke)."""

from __future__ import annotations

import os
import sys


def main() -> int:
    if not (os.getenv("DOTTLE_API_KEY") or "").strip():
        print("Set DOTTLE_API_KEY to run Dottle scenarios.", file=sys.stderr)
        print("Optional: DOTTLE_URL (default includes /api/v1).", file=sys.stderr)
        return 1

    os.environ["DOTTLE_TEST_SYNC"] = "1"

    from tests.dottle_platform.scenarios import SCENARIOS

    failed: list[str] = []
    for name, fn in SCENARIOS:
        try:
            fn()
            print(f"ok  {name}")
        except AssertionError as e:
            print(f"FAIL {name}: {e}", file=sys.stderr)
            failed.append(name)
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {name}: {e!r}", file=sys.stderr)
            failed.append(name)

    if failed:
        print(f"\n{len(failed)} scenario(s) failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    print(f"\nAll {len(SCENARIOS)} scenarios passed. Check the Dottle dashboard for new sessions/spans.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
