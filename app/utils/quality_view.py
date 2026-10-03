"""
RecallScope — Quality & Integrity page

Shows the latest audit. Opening this page does not call Groq and does not
rewrite research files.
"""

from typing import Any, Dict

import streamlit as st

from app.utils.quality_audit import run_quality_audit


def render_quality_integrity() -> None:
    """Run and display the Phase 8 audit."""
    st.markdown("### Quality & Integrity")
    st.write("This audit checks whether the saved Discovery Engine is traceable, conservative, and internally consistent.")
    report = run_quality_audit()
    _summary(report)
    for check in report["checks"]:
        _card(check)
    st.markdown("#### What this audit does NOT prove")
    st.info(
        "Passing technical and integrity checks does not make the corpus representative, "
        "and it does not validate a final product problem or a product solution."
    )
    for line in report["does_not_prove"]:
        st.markdown(f"- {line}")


def _summary(report: Dict[str, Any]) -> None:
    overall = report["overall"]
    if overall == "FAIL":
        st.error(f"Overall audit status: {overall}")
    elif overall == "WARNING":
        st.warning(f"Overall audit status: {overall}")
    else:
        st.success(f"Overall audit status: {overall}")
    st.info(
        "A warning does not mean the system is broken. "
        "It means the research contains limitations or uncertainty that should remain visible."
    )
    columns = st.columns(4)
    columns[0].metric("Checks passed", report["passed"])
    columns[1].metric("Warnings", report["warnings"])
    columns[2].metric("Failures", report["failures"])
    columns[3].metric("Checks run", len(report["checks"]))
    st.caption(f"Latest audit: {report['timestamp']}")


def _card(check: Dict[str, Any]) -> None:
    status = check["status"]
    title = f"Check {check['check_id']} — {check['name']} — {status}"
    with st.expander(title, expanded=status != "PASS"):
        if status == "FAIL":
            st.error(status)
        elif status == "WARNING":
            st.warning(status)
        else:
            st.success(status)
        st.write(check["explanation"])
        for detail in check["details"]:
            st.markdown(f"- {detail}")
        if check["record_ids"]:
            shown = check["record_ids"][:24]
            extra = len(check["record_ids"]) - len(shown)
            suffix = f" (+{extra} more)" if extra else ""
            st.caption("Affected record IDs: " + ", ".join(shown) + suffix)
