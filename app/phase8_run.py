"""
RecallScope — Phase 8 audit runner

Runs the quality and integrity checks. Does not call Groq and does not
rewrite research files.
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.utils.quality_audit import run_quality_audit


def main() -> int:
    report = run_quality_audit()
    print(f"OVERALL {report['overall']}")
    print(f"TIMESTAMP {report['timestamp']}")
    print(f"PASSED {report['passed']} WARNINGS {report['warnings']} FAILURES {report['failures']}")
    for check in report["checks"]:
        print(f"CHECK {check['check_id']} {check['status']} {check['name']}")
        for detail in check["details"]:
            print(f"  - {detail}")
        if check["record_ids"]:
            print("  IDs " + ", ".join(check["record_ids"][:30]))
    dumped = str(report)
    if "gsk_" in dumped:
        print("SECRET APPEARED IN REPORT")
        return 1
    return 0 if report["failures"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
