"""
RecallScope — Phase 4 Streamlit section

Renders research analysis calculated from the audited classification file.
Rendering this section does not call the LLM and does not modify evidence.
"""

from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from app.utils.research_analysis import CORPUS_SHARE_LABEL, build_research_analysis


def render_phase4_section() -> None:
    """Render Phase 4 from the corrected classified dataset."""
    st.subheader("Phase 4 — Research Analysis")
    st.caption(
        "Cross-record patterns are calculated from the audited Phase 3 classifications. "
        "Opening this section does not reclassify evidence."
    )

    analysis = build_research_analysis()
    st.caption("Saved analysis artifact: `data/research_analysis.json`. Opening this page does not rewrite it.")

    st.info(analysis["disclaimer"])
    st.caption(f"Every percentage below is a {CORPUS_SHARE_LABEL.lower()}, not a population rate.")

    overview, journey, behaviour, memory, patterns, candidates, contradictions, limitations = st.tabs([
        "Overview",
        "Failure journey",
        "Retrieval behaviour",
        "Memory clues",
        "Pattern cards",
        "Candidate problem areas",
        "Contradictions",
        "Research limitations",
    ])

    with overview:
        _render_overview(analysis)
    with journey:
        _render_journey(analysis)
    with behaviour:
        _render_behaviours(analysis)
    with memory:
        _render_memory(analysis)
    with patterns:
        _render_patterns(analysis)
    with candidates:
        _render_candidates(analysis)
    with contradictions:
        _render_contradictions(analysis)
    with limitations:
        _render_limitations(analysis)

    _render_trace(analysis)


def _render_overview(analysis: Dict[str, Any]) -> None:
    st.markdown("#### Research Analysis Overview")
    summary = analysis["input"]
    columns = st.columns(4)
    columns[0].metric("Classified evidence", summary["classified_record_count"])
    columns[1].metric("Raw corpus", summary["raw_record_count"])
    columns[2].metric("Needs human review", summary["human_review_count"])
    columns[3].metric("Uncertain, not classified", len(summary["uncertain_record_ids"]))

    st.markdown("#### Failure-stage distribution")
    st.caption(CORPUS_SHARE_LABEL)
    stage_frame = _stage_frame(analysis)
    st.bar_chart(stage_frame.set_index("failure_stage")[["records"]], horizontal=True)
    st.dataframe(stage_frame, use_container_width=True, hide_index=True)

    left, right = st.columns(2)
    with left:
        st.markdown("#### Evidence-strength distribution")
        st.dataframe(
            _count_frame(summary["evidence_strength_distribution"], "evidence_strength", "records"),
            use_container_width=True,
            hide_index=True,
        )
    with right:
        st.markdown("#### Source distribution")
        st.dataframe(
            _count_frame(summary["source_distribution"], "source", "records"),
            use_container_width=True,
            hide_index=True,
        )
    if not analysis["failure_stage_count_check"]["matches"]:
        st.error("Failure-stage counts do not add up to the classified record count.")


def _render_journey(analysis: Dict[str, Any]) -> None:
    st.markdown("#### Failure Journey Analysis")
    st.caption("Stages with no records were not observed in this classified corpus.")
    for stage in analysis["failure_stages"]:
        count = stage["record_count"]
        label = f"{stage['failure_stage']} — {stage['share']['display']}"
        with st.expander(label):
            st.markdown(
                f"**Human review:** {stage['human_review_count']}  \n"
                f"**Evidence strength:** {_format_mix(stage['evidence_strength_mix'])}  \n"
                f"**Sources:** {_format_mix(stage['source_mix'])}"
            )
            if stage["supporting_record_ids"]:
                st.markdown("**Supporting records:** " + ", ".join(stage["supporting_record_ids"]))
                _render_record_traces(analysis, stage["supporting_record_ids"], f"stage-{stage['failure_stage']}")
            else:
                st.caption("No classified record uses this stage. That absence is not evidence the stage never occurs.")


def _render_behaviours(analysis: Dict[str, Any]) -> None:
    st.markdown("#### Retrieval Behaviour Analysis")
    st.caption("Unknown means the behaviour was not established. It is not counted as No.")
    rows = []
    for item in analysis["behaviours"]:
        contradicted = item["explicitly_contradicted_count"]
        rows.append({
            "behaviour": item["behaviour"],
            "explicitly_supported": item["explicitly_supported_count"],
            "explicit_no": "—" if contradicted is None else contradicted,
            "not_established": item["not_established_count"],
            "small_count_note": item["small_count_note"],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    selected = st.selectbox(
        "Inspect one behaviour",
        [item["behaviour"] for item in analysis["behaviours"]],
        key="phase4_behaviour",
    )
    item = next(entry for entry in analysis["behaviours"] if entry["behaviour"] == selected)
    st.markdown(item["note"])
    st.markdown("**Supported records:** " + (", ".join(item["explicitly_supported_record_ids"]) or "None"))
    if item["explicitly_contradicted_record_ids"]:
        st.markdown("**Explicit No records:** " + ", ".join(item["explicitly_contradicted_record_ids"]))
    if item["small_count_note"]:
        st.warning(item["small_count_note"])


def _render_memory(analysis: Dict[str, Any]) -> None:
    st.markdown("#### Memory Clue Analysis")
    memory = analysis["memory_clues"]
    st.info(memory["schema_note"])
    columns = st.columns(4)
    columns[0].metric("Remembered clues stated", memory["remembered_clues_stated_count"])
    columns[1].metric("Remembered clues unknown", memory["remembered_clues_unknown_count"])
    columns[2].metric("Forgotten clues stated", memory["forgotten_clues_stated_count"])
    columns[3].metric("Forgotten clues unknown", memory["forgotten_clues_unknown_count"])

    st.markdown("#### Saved clue text")
    st.caption("Each row is the classification text, not a new category.")
    if memory["saved_clue_phrases"]:
        st.dataframe(pd.DataFrame(memory["saved_clue_phrases"]), use_container_width=True, hide_index=True)
    else:
        st.info("No substantive clue text is saved.")

    st.markdown("#### Comparison labels matched to saved clue text")
    st.caption(CORPUS_SHARE_LABEL)
    for group in memory["comparison_groups"]:
        with st.expander(f"{group['comparison_label']} — {group['record_count']} records"):
            st.markdown(group["absence_note"])
            st.markdown(
                f"**Share:** {group['share']['display']}  \n"
                f"**Evidence strength:** {_format_mix(group['evidence_strength_mix'])}  \n"
                f"**Failure stages:** {_format_mix(group['failure_stage_mix'])}"
            )
            if group["supporting_record_ids"]:
                st.markdown("**Records:** " + ", ".join(group["supporting_record_ids"]))
            if group["small_count_note"]:
                st.warning(group["small_count_note"])
            if group["matches"]:
                st.dataframe(pd.DataFrame(group["matches"]), use_container_width=True, hide_index=True)


def _render_patterns(analysis: Dict[str, Any]) -> None:
    st.markdown("#### Pattern Cards")
    st.caption("Cards are emitted only when at least two classified records meet the same evidence rule.")
    if not analysis["pattern_cards"]:
        st.info("No pattern met the two-record minimum.")
        return
    for card in analysis["pattern_cards"]:
        with st.expander(f"{card['pattern_name']} — {card['supporting_record_count']} records — {card['confidence']} confidence"):
            st.markdown(card["what_was_observed"])
            st.markdown(f"**Share:** {card['share']['display']} — {card['share']['label']}")
            st.markdown("**Supporting records:** " + ", ".join(card["supporting_record_ids"]))
            st.markdown(
                f"**Sources:** {_format_mix(card['source_mix'])}  \n"
                f"**Evidence strength:** {_format_mix(card['evidence_strength_mix'])}  \n"
                f"**Failure stages:** {_format_mix(card['failure_stage_mix'])}"
            )
            if card["small_count_note"]:
                st.warning(card["small_count_note"])
            st.markdown("**What the evidence supports**")
            st.write(card["what_the_evidence_supports"])
            st.markdown("**What the evidence does not establish**")
            st.write(card["what_the_evidence_does_not_establish"])
            st.markdown("**Contradictory or limiting evidence**")
            st.write(card["contradictory_or_limiting_evidence"])
            for example in card["example_excerpts"]:
                st.markdown(f"`{example['record_id']}` — {example['source']} — {example['evidence_strength']}")
                st.markdown(f"> {example['excerpt']}")
                _link(example["source_url"])
            _render_record_traces(analysis, card["supporting_record_ids"], card["pattern_name"])


def _render_candidates(analysis: Dict[str, Any]) -> None:
    st.markdown("#### Candidate Problem Areas")
    st.warning(
        "These candidates are not ranked, and none is selected. "
        "They are not a final problem statement and they are not a product recommendation."
    )
    if not analysis["candidate_problem_areas"]:
        st.info("No candidate reached the minimum evidence count.")
        return
    for candidate in analysis["candidate_problem_areas"]:
        with st.expander(
            f"{candidate['candidate_problem_area']} — {candidate['supporting_record_count']} records — {candidate['confidence']} confidence"
        ):
            st.write(candidate["evidence_supported_description"])
            st.markdown("**Supporting records:** " + ", ".join(candidate["supporting_record_ids"]))
            st.markdown(
                f"**Evidence strength:** {_format_mix(candidate['evidence_strength_profile'])}  \n"
                f"**Failure stages:** {_format_mix(candidate['failure_stage_mix'])}"
            )
            if candidate["small_count_note"]:
                st.warning(candidate["small_count_note"])
            st.markdown(f"**Observed behaviours:** {candidate['relevant_observed_behaviours']}")
            st.markdown(f"**Consequence visible in the evidence:** {candidate['user_consequence_visible_in_evidence']}")
            st.markdown(f"**Alternative explanation:** {candidate['alternative_explanation']}")
            st.markdown(f"**Evidence gaps:** {candidate['evidence_gaps']}")
            _render_record_traces(analysis, candidate["supporting_record_ids"], candidate["candidate_problem_area"])


def _render_contradictions(analysis: Dict[str, Any]) -> None:
    section = analysis["contradictions_and_evidence_gaps"]
    st.markdown(f"#### {section['title']}")
    st.caption("These items are here to keep a finding from looking stronger than the records underneath it.")
    for item in section["challenges"]:
        with st.expander(f"{item['challenge']} — {item['record_count']} records"):
            st.write(item["detail"])
            if item["supporting_record_ids"]:
                st.markdown("**Records:** " + ", ".join(item["supporting_record_ids"]))
                _render_record_traces(analysis, item["supporting_record_ids"], item["challenge"])


def _render_limitations(analysis: Dict[str, Any]) -> None:
    st.markdown("#### Research Limitations")
    for limitation in analysis["research_limitations"]:
        st.markdown(f"- {limitation}")


def _render_trace(analysis: Dict[str, Any]) -> None:
    st.markdown("#### Trace a record")
    st.caption("Move from a record ID to the original evidence and the source URL.")
    index = analysis["trace_index"]
    if not index:
        st.info("No classified records are available to trace.")
        return
    selected = st.selectbox(
        "Record ID",
        [row["record_id"] for row in index],
        key="phase4_trace_record",
    )
    _render_one_trace(next(row for row in index if row["record_id"] == selected), "trace")


def _render_record_traces(analysis: Dict[str, Any], record_ids: List[str], key_prefix: str) -> None:
    lookup = {row["record_id"]: row for row in analysis["trace_index"]}
    for record_id in record_ids:
        row = lookup.get(record_id)
        if row is None:
            st.error(f"{record_id} is not in the classified corpus.")
            continue
        st.markdown(f"**Original evidence — {record_id}**")
        _render_one_trace(row, f"{key_prefix}-{record_id}")


def _render_one_trace(row: Dict[str, Any], key_prefix: str) -> None:
    review = "Needs human review" if row["needs_human_review"] else "Human review not flagged"
    st.markdown(
        f"**{row['record_id']}** · {row['source']} · {row['date']}  \n"
        f"**Stage:** {row['primary_failure_stage']}  \n"
        f"**Evidence strength:** {row['evidence_strength']}  \n"
        f"**Outcome:** {row['retrieval_outcome']}  \n"
        f"**Review:** {review}"
    )
    st.text_area(
        f"Original text {row['record_id']}",
        value=row["original_text"],
        height=140,
        disabled=True,
        label_visibility="collapsed",
        key=f"phase4_text_{key_prefix}",
    )
    _link(row["source_url"])


def _link(url: str) -> None:
    if str(url).startswith("http://") or str(url).startswith("https://"):
        st.markdown(f"[Open source URL]({url})")
    else:
        st.markdown(f"**Source URL:** `{url}`")


def _stage_frame(analysis: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for stage in analysis["failure_stages"]:
        rows.append({
            "failure_stage": stage["failure_stage"],
            "records": stage["record_count"],
            "share": stage["share"]["display"],
            "evidence_strength": _format_mix(stage["evidence_strength_mix"]),
            "sources": _format_mix(stage["source_mix"]),
            "human_review": stage["human_review_count"],
        })
    return pd.DataFrame(rows)


def _count_frame(counts: Dict[str, int], label: str, value_name: str) -> pd.DataFrame:
    rows = [{label: key, value_name: value} for key, value in counts.items()]
    if not rows:
        return pd.DataFrame(columns=[label, value_name])
    return pd.DataFrame(rows)


def _format_mix(mix: Dict[str, int]) -> str:
    if not mix:
        return "None"
    return "; ".join(f"{key}: {value}" for key, value in mix.items())
