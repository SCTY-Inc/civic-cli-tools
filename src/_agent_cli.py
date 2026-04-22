"""Minimal CLI doctor helpers used by civic."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable


@dataclass
class DoctorCheck:
    name: str
    check: Callable[[], bool]
    hint: str | None = None


DoctorCheckInput = (
    DoctorCheck
    | tuple[str, Callable[[], bool]]
    | tuple[str, Callable[[], bool], str | None]
)


def doctor_runner(
    checks: list[DoctorCheckInput],
    *,
    exit_on_fail: bool = True,
) -> int:
    """Run doctor checks, print status, and return an exit code."""
    normalized: list[DoctorCheck] = []
    for item in checks:
        if isinstance(item, DoctorCheck):
            normalized.append(item)
            continue
        name, check, *rest = item
        normalized.append(DoctorCheck(name=name, check=check, hint=rest[0] if rest else None))

    failures = 0
    width = max((len(check.name) for check in normalized), default=0)
    for check in normalized:
        try:
            ok = bool(check.check())
            hint = check.hint or ""
        except Exception as error:
            ok = False
            hint = f"{check.hint or ''} ({error})".strip()

        mark = "PASS" if ok else "FAIL"
        line = f"  [{mark}] {check.name.ljust(width)}"
        if not ok and hint:
            line += f"  — {hint}"
        print(line, file=sys.stderr)
        failures += int(not ok)

    if failures:
        print(f"\ndoctor: {failures} check(s) failed", file=sys.stderr)
        if exit_on_fail:
            sys.exit(1)
        return 1

    print("\ndoctor: all checks passed", file=sys.stderr)
    return 0
