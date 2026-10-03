"""
RecallScope — Phase 5 Discovery Interface

Reads saved research artifacts. Opening this interface does not classify
evidence and does not rewrite the Phase 4 analysis file.
"""

from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from app.utils.ask_evidence_view import render_ask_evidence
from app.utils.challenge_insight_view import render_challenge_insight
from app.utils.quality_view import render_quality_integrity
from app.utils.discovery_data import (
    INTERIM_CORPUS_LABEL,
    SHARE_LABEL,
    STAGE_MEANINGS,
    classified_records,
    count_by,
    load_discovery_records,
    load_research_analysis,
)

DISCOVERY_SECTIONS = [
    "Research overview",
    "Contradictions and gaps",
    "Failure explorer",
    "Memory and behaviour",
    "Pattern explorer",
    "Candidate problem areas",
    "Evidence explorer",
    "Ask the Evidence",
    "Challenge an Insight",
    "Methodology",
    "Quality & Integrity",
]

WORKFLOW_STEPS = [
    "Public evidence",
    "Relevance filtering",
    "AI structured classification",
    "Cross-record pattern analysis",
    "Evidence-grounded exploration",
    "Challenge and contradiction testing",
]


def inject_styles() -> None:
    """Apply quiet layout styles. Does not change research data."""
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1080px; }
        [data-testid="stSidebar"] { border-right: 1px solid #e6e1d8; }
        [data-testid="stSidebar"] h1 { font-size: 1.45rem; font-weight: 650; letter-spacing: -0.02em; }
        section[data-testid="stSidebar"] div[role="radiogroup"] label {
            border-radius: 8px;
            padding: 0.12rem 0.35rem;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
            background: #e7efe9;
            font-weight: 650;
        }
        div[data-testid="stMetric"] {
            border: 1px solid rgba(140, 132, 120, 0.45);
            border-radius: 10px;
            padding: 0.55rem 0.7rem 0.35rem;
        }
        div[data-testid="stDataFrame"] { max-width: 100%; }
        .rs-flow { display: flex; flex-wrap: wrap; align-items: center; gap: 0.35rem 0.3rem; margin: 0.8rem 0 1.1rem; }
        .rs-step {
            background: #f7f5f0;
            border: 1px solid #e4ddd2;
            border-radius: 8px;
            padding: 0.42rem 0.65rem;
            font-size: 0.92rem;
            line-height: 1.35;
            color: #1c2430;
        }
        .rs-step span { margin-right: 0.35rem; color: #3d5c4a; font-weight: 700; }
        .rs-arrow { color: #8d8478; padding: 0 0.05rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_discovery(section: str) -> None:
    """Render one Discovery Engine section from the saved artifacts."""
    records = load_discovery_records()
    analysis = load_research_analysis()
    lookup = {record["record_id"]: record for record in records}

    if section == "Research overview":
        _hero()
        _how_ai_is_used()
        _overview(records, analysis)
    else:
        st.caption("RecallScope · Interim public-evidence corpus — not representative of all Google Photos users")
        if section == "Contradictions and gaps":
            _contradictions(analysis, lookup)
        elif section == "Failure explorer":
            _failure_explorer(records)
        elif section == "Memory and behaviour":
            _memory(analysis, lookup)
        elif section == "Pattern explorer":
            _patterns(analysis, lookup)
        elif section == "Candidate problem areas":
            _candidates(analysis, lookup)
        elif section == "Evidence explorer":
            _evidence(records)
        elif section == "Ask the Evidence":
            render_ask_evidence(records, analysis)
        elif section == "Challenge an Insight":
            render_challenge_insight(records, analysis)
        elif section == "Methodology":
            _methodology(analysis)
        elif section == "Quality & Integrity":
            render_quality_integrity()
        else:
            st.info("Choose a section from the sidebar.")


def _hero() -> None:
    st.title("RecallScope")
    st.subheader("AI-powered discovery engine for vague-memory photo retrieval research.")
    st.warning(INTERIM_CORPUS_LABEL)
    st.write(
        "People sometimes know a photo exists but cannot describe it precisely enough to find it. "
        "RecallScope studies public posts about that problem and keeps every finding tied to the original wording."
    )
    steps = []
    for index, step in enumerate(WORKFLOW_STEPS):
        steps.append(f'<div class="rs-step"><span>{index + 1}</span>{step}</div>')
        if index < len(WORKFLOW_STEPS) - 1:
            steps.append('<div class="rs-arrow">→</div>')
    st.markdown(f'<div class="rs-flow">{"".join(steps)}</div>', unsafe_allow_html=True)
    st.caption("This path describes the saved research workflow. It does not mean the posts represent all Google Photos users.")


def _how_ai_is_used() -> None:
    with st.expander("How AI is used"):
        left, right = st.columns(2)
        with left:
            st.markdown("**What AI does**")
            st.markdown(
                """
- Structures relevant public posts into research fields, such as clues, behaviour, and a failure stage.
- Looks across those saved fields for candidate patterns.
- Answers a question only after relevant saved records have been retrieved.
- Tests a proposed insight by searching for evidence that supports it and evidence that weakens it.
                """
            )
        with right:
            st.markdown("**What AI does not do**")
            st.markdown(
                """
- It does not invent missing user details.
- It does not treat Unknown as No.
- It does not automatically make a final product decision.
- It does not turn a count in this corpus into population prevalence.
                """
            )
        st.caption("The original post stays available beside any AI interpretation. Human review flags stay visible.")


BEHAVIOUR_FIELDS = {
    "Query or search attempt described in search_or_browse_behavior": "search_or_browse_behavior",
    "Query reformulation described in reformulation_behavior": "reformulation_behavior",
    "Manual browsing described in manual_browsing_behavior": "manual_browsing_behavior",
    "manual_scroll_signal": "manual_scroll_signal",
    "candidate_overload_signal": "candidate_overload_signal",
    "recognition_difficulty_signal": "recognition_difficulty_signal",
    "query_difficulty_signal": "query_difficulty_signal",
    "Remembered clues stated": "remembered_clues",
    "Forgotten or uncertain clues stated": "missing_or_forgotten_clues",
    "Workaround stated": "workaround",
    "Human review required": "needs_human_review",
    "Retrieval outcome: Found": "retrieval_outcome",
    "Retrieval outcome: Not Found": "retrieval_outcome",
    "Retrieval outcome: Partially Found": "retrieval_outcome",
    "Retrieval outcome: Gave Up": "retrieval_outcome",
    "Retrieval outcome: Unknown": "retrieval_outcome",
}


def _overview(records: List[Dict[str, Any]], analysis: Dict[str, Any]) -> None:
    st.markdown("### Corpus at a glance")
    st.caption("Counts describe this saved corpus. They are not population prevalence.")
    st.caption(analysis.get("disclaimer", ""))
    classified = classified_records(records)
    relevant = sum(1 for record in records if record["relevance_label"] == "Relevant")
    uncertain = [record for record in records if record["relevance_label"] == "Uncertain"]
    review_count = sum(1 for record in classified if record["needs_human_review"])
    sources = count_by(records, "source")

    columns = st.columns(4)
    columns[0].metric("Raw public records", len(records))
    columns[1].metric("Relevant records", relevant)
    columns[2].metric("Uncertain records", len(uncertain))
    columns[3].metric("AI-classified records", len(classified))

    second = st.columns(3)
    second[0].metric("Sources", len(sources))
    second[1].metric("Needs human review", review_count)
    second[2].metric("Contradictions logged", len(analysis["contradictions_and_evidence_gaps"]["challenges"]))

    st.markdown("#### Sources in the raw corpus")
    st.dataframe(_count_frame(sources, "source", "records"), use_container_width=True, hide_index=True)

    st.markdown("#### Evidence strength of the classified records")
    st.caption(SHARE_LABEL)
    st.dataframe(
        _count_frame(count_by(classified, "evidence_strength"), "evidence_strength", "records"),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("#### Where the audited records sit")
    st.caption(SHARE_LABEL)
    st.caption(
        "A failure stage is an interpretation of the post, not a proven cause. "
        "F8 means the post does not support a specific stage. Unknown was not turned into a cause."
    )
    st.dataframe(_stage_frame(analysis), use_container_width=True, hide_index=True)

    if uncertain:
        st.markdown("#### Uncertain records kept outside automatic classification")
        for record in uncertain:
            st.markdown(f"**{record['record_id']}** — {record['source']}")
            st.caption(record["relevance_reason"])

    challenge_count = len(analysis["contradictions_and_evidence_gaps"]["challenges"])
    st.info(
        f"{challenge_count} contradiction and evidence-gap notes are saved from the approved analysis. "
        "Open “Contradictions and gaps” before treating any pattern as a conclusion. "
        f"{review_count} classified records still need human review."
    )


def _failure_explorer(records: List[Dict[str, Any]]) -> None:
    st.markdown("### Failure explorer")
    st.caption(
        "These labels describe where a saved post appears to break. "
        "A count is a share of this interim corpus, not a rate among all users. "
        "No failure stage is treated as the final root cause."
    )
    with st.expander("What the stage labels mean"):
        for stage, meaning in STAGE_MEANINGS.items():
            st.markdown(f"**{stage}.** {meaning}")
    classified = classified_records(records)
    filters = st.columns(3)
    stage = filters[0].selectbox("Failure stage", _options(classified, "primary_failure_stage", "All stages"), key="disc_stage")
    source = filters[1].selectbox("Source", _options(classified, "source", "All sources"), key="disc_source")
    photo = filters[2].selectbox("Photo type", _options(classified, "photo_type", "All photo types"), key="disc_photo")
    more = st.columns(3)
    strength = more[0].selectbox("Evidence strength", _options(classified, "evidence_strength", "All strengths"), key="disc_strength")
    outcome = more[1].selectbox("Outcome", _options(classified, "retrieval_outcome", "All outcomes"), key="disc_outcome")
    review = more[2].selectbox("Human review", ["All review statuses", "Needs human review", "Not flagged"], key="disc_review")

    filtered = _apply_failure_filters(classified, stage, source, photo, strength, outcome, review)
    st.markdown(f"**{len(filtered)} of {len(classified)} classified records** in this interim corpus.")
    if stage in STAGE_MEANINGS:
        st.caption(f"What this label means: {STAGE_MEANINGS[stage]}")

    if not filtered:
        st.info("No classified records match these filters.")
        return

    st.dataframe(
        _failure_table(filtered),
        use_container_width=True,
        hide_index=True,
        column_config={
            "record_id": st.column_config.TextColumn("Record", width="small"),
            "source": st.column_config.TextColumn("Source", width="small"),
            "failure_stage": st.column_config.TextColumn("Stage", width="medium"),
            "photo_type": st.column_config.TextColumn("Photo type", width="small"),
            "outcome": st.column_config.TextColumn("Outcome", width="small"),
            "evidence_strength": st.column_config.TextColumn("Strength", width="small"),
            "human_review": st.column_config.TextColumn("Review", width="small"),
        },
    )
    selected = st.selectbox("Inspect a filtered record", [record["record_id"] for record in filtered], key="disc_failure_record")
    _record_panel(next(record for record in filtered if record["record_id"] == selected), "failure")


def _memory(analysis: Dict[str, Any], lookup: Dict[str, Dict[str, Any]]) -> None:
    st.markdown("### Memory and behaviour")
    st.caption(
        "Values come from the audited classification fields and the saved Phase 4 summary. "
        "Unknown stays Unknown. A blank in the original post was not turned into No."
    )
    behaviours = analysis["behaviours"]
    selected_name = st.selectbox("Saved behaviour summary", [item["behaviour"] for item in behaviours], key="disc_behaviour")
    item = next(entry for entry in behaviours if entry["behaviour"] == selected_name)
    contradicted = item["explicitly_contradicted_count"]
    columns = st.columns(3)
    columns[0].metric("Explicitly supported", item["explicitly_supported_count"])
    columns[1].metric("Explicit No", "—" if contradicted is None else contradicted)
    columns[2].metric("Not established", item["not_established_count"])
    st.write(item["note"])
    if item["small_count_note"]:
        st.warning(item["small_count_note"])
    st.markdown("**Supported record IDs:** " + (", ".join(item["explicitly_supported_record_ids"]) or "None"))
    if item["explicitly_contradicted_record_ids"]:
        st.markdown("**Explicit No record IDs:** " + ", ".join(item["explicitly_contradicted_record_ids"]))

    field = BEHAVIOUR_FIELDS.get(selected_name, "")
    rows = []
    for record_id in item["explicitly_supported_record_ids"]:
        record = lookup.get(record_id)
        if record is None:
            continue
        rows.append({
            "record_id": record_id,
            "saved_field": field or "see classification",
            "saved_value": _field_text(record, field),
            "outcome": record["retrieval_outcome"],
            "failure_stage": record["primary_failure_stage"],
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        chosen = st.selectbox("Open supporting evidence", [row["record_id"] for row in rows], key="disc_memory_record")
        _record_panel(lookup[chosen], "memory")

    st.markdown("#### Saved clue text")
    st.caption("Each row is the audited clue field. It is not a new set of memory categories.")
    phrases = analysis["memory_clues"]["saved_clue_phrases"]
    if phrases:
        st.dataframe(pd.DataFrame(phrases), use_container_width=True, hide_index=True)
    else:
        st.info("No substantive clue text was saved.")

    stated = analysis["memory_clues"]["remembered_clues_stated_count"]
    unknown = analysis["memory_clues"]["remembered_clues_unknown_count"]
    forgotten = analysis["memory_clues"]["forgotten_clues_stated_count"]
    forgotten_unknown = analysis["memory_clues"]["forgotten_clues_unknown_count"]
    st.caption(
        f"Remembered clues stated: {stated}. Remembered clues Unknown: {unknown}. "
        f"Forgotten clues stated: {forgotten}. Forgotten clues Unknown: {forgotten_unknown}."
    )


def _patterns(analysis: Dict[str, Any], lookup: Dict[str, Dict[str, Any]]) -> None:
    st.markdown("### Pattern explorer")
    st.caption(
        "These are the approved pattern cards. No new patterns are added here. "
        "Trace each card from the record IDs to a verbatim excerpt and the original source link."
    )
    cards = analysis["pattern_cards"]
    if not cards:
        st.info("The saved analysis has no pattern cards.")
        return
    for card in cards:
        title = f"{card['pattern_name']} — {card['supporting_record_count']} records — {card['confidence']} confidence"
        with st.expander(title):
            st.markdown(card["what_was_observed"])
            st.markdown(f"**Share:** {card['share']['display']} — {card['share']['label']}")
            st.markdown(
                f"**Evidence strength:** {_format_mix(card['evidence_strength_mix'])}  \n"
                f"**Sources:** {_format_mix(card['source_mix'])}"
            )
            st.markdown("**Supporting records:** " + ", ".join(card["supporting_record_ids"]))
            if card.get("small_count_note"):
                st.warning(card["small_count_note"])
            st.markdown("**What the evidence supports**")
            st.write(card["what_the_evidence_supports"])
            st.markdown("**What the evidence does not establish**")
            st.write(card["what_the_evidence_does_not_establish"])
            st.markdown("**Limiting evidence**")
            st.write(card["contradictory_or_limiting_evidence"])
            for example in card["example_excerpts"]:
                st.markdown(f"`{example['record_id']}`")
                st.markdown(f"> {example['excerpt']}")
                _source_link(example.get("source_url", ""))
            _open_buttons(card["supporting_record_ids"], lookup, f"pattern-{card['pattern_name']}")


def _candidates(analysis: Dict[str, Any], lookup: Dict[str, Dict[str, Any]]) -> None:
    st.markdown("### Candidate problem areas")
    st.warning(
        "These areas are not ranked. They are not final problem statements. "
        "They are not product recommendations. They still need triangulation with primary research, "
        "such as interviews or a survey."
    )
    for candidate in analysis["candidate_problem_areas"]:
        title = (
            f"{candidate['candidate_problem_area']} — "
            f"{candidate['supporting_record_count']} records — {candidate['confidence']} confidence"
        )
        with st.expander(title):
            st.write(candidate["evidence_supported_description"])
            st.markdown("**Supporting records:** " + ", ".join(candidate["supporting_record_ids"]))
            st.markdown(f"**Evidence strength:** {_format_mix(candidate['evidence_strength_profile'])}")
            if candidate.get("small_count_note"):
                st.warning(candidate["small_count_note"])
            st.markdown(f"**Behaviours visible in the saved fields:** {candidate['relevant_observed_behaviours']}")
            st.markdown(f"**Consequence described in the evidence:** {candidate['user_consequence_visible_in_evidence']}")
            st.markdown(f"**Alternative explanation:** {candidate['alternative_explanation']}")
            st.markdown(f"**Evidence gaps:** {candidate['evidence_gaps']}")
            _open_buttons(candidate["supporting_record_ids"], lookup, f"candidate-{candidate['candidate_problem_area']}")


def _contradictions(analysis: Dict[str, Any], lookup: Dict[str, Dict[str, Any]]) -> None:
    section = analysis["contradictions_and_evidence_gaps"]
    st.markdown("### Contradictions and evidence gaps")
    st.error(
        "Read this before drawing a conclusion. Several findings describe what a post says. "
        "They do not establish a single cause, and they do not describe all Google Photos users."
    )
    for item in section["challenges"]:
        with st.expander(f"{item['challenge']} — {item['record_count']} records"):
            st.write(item["detail"])
            if item["supporting_record_ids"]:
                st.markdown("**Records:** " + ", ".join(item["supporting_record_ids"]))
                _open_buttons(item["supporting_record_ids"], lookup, f"gap-{item['challenge']}")
    review_ids = [
        record_id for record_id, record in lookup.items()
        if record["classified"] and record["needs_human_review"]
    ]
    st.markdown("#### Classified records that still need human review")
    st.caption(f"{len(review_ids)} of {sum(1 for record in lookup.values() if record['classified'])} classified records.")
    st.markdown(", ".join(review_ids) if review_ids else "None")


def _evidence(records: List[Dict[str, Any]]) -> None:
    st.markdown("### Evidence explorer")
    st.caption(
        "Read the person's words first. The classification beside them is an interpretation. "
        "The summary does not replace the post. Each record keeps its ID and source link."
    )
    filters = st.columns(3)
    sources = ["All sources"] + sorted({record["source"] for record in records})
    labels = ["All relevance decisions"] + sorted({record["relevance_label"] for record in records if record["relevance_label"]})
    source = filters[0].selectbox("Source", sources, key="disc_evidence_source")
    label = filters[1].selectbox("Relevance", labels, key="disc_evidence_label")
    query = filters[2].text_input("Search the original wording", key="disc_evidence_search")

    filtered = records
    if source != "All sources":
        filtered = [record for record in filtered if record["source"] == source]
    if label != "All relevance decisions":
        filtered = [record for record in filtered if record["relevance_label"] == label]
    if query.strip():
        needle = query.strip().lower()
        filtered = [record for record in filtered if needle in record["original_text"].lower()]

    st.markdown(f"**{len(filtered)} of {len(records)} raw records.**")
    if not filtered:
        st.info("No records match this search.")
        return

    st.dataframe(
        _evidence_table(filtered),
        use_container_width=True,
        hide_index=True,
        column_config={
            "record_id": st.column_config.TextColumn("Record", width="small"),
            "source": st.column_config.TextColumn("Source", width="medium"),
            "date": st.column_config.TextColumn("Date", width="small"),
            "relevance": st.column_config.TextColumn("Relevance", width="small"),
            "failure_stage": st.column_config.TextColumn("Stage", width="medium"),
            "original_text": st.column_config.TextColumn("Original text", width="large"),
        },
    )
    ids = [record["record_id"] for record in filtered]
    preferred = st.session_state.get("disc_evidence_record")
    if preferred not in ids:
        st.session_state["disc_evidence_record"] = ids[0]
    selected = st.selectbox("Record", ids, key="disc_evidence_record")
    _record_panel(next(record for record in filtered if record["record_id"] == selected), "evidence")


def _methodology(analysis: Dict[str, Any]) -> None:
    st.markdown("### Methodology and research integrity")
    st.markdown(
        """
1. Public evidence was collected and stored verbatim.
2. The dataset was validated without changing the original wording.
3. Each record was marked Relevant, Irrelevant, or Uncertain.
4. Relevant records received an AI classification. Uncertain records did not.
5. Those classifications were quality-audited and corrected where the evidence did not support them.
6. Cross-record analysis counted only the audited fields.
7. This Discovery Interface reads those saved results.
        """
    )
    columns = st.columns(3)
    columns[0].markdown("**Original evidence**")
    columns[0].write("The post text, date, source, and source link. This is what the person wrote.")
    columns[1].markdown("**AI interpretation**")
    columns[1].write("The audited classification: failure stage, clues, behaviours, outcome, and review flag. It is an interpretation.")
    columns[2].markdown("**Aggregated analysis**")
    columns[2].write("Counts, pattern cards, and candidate areas calculated from the audited rows. They describe this corpus only.")

    st.markdown("#### Limitations that stay in view")
    for limitation in analysis["research_limitations"]:
        st.markdown(f"- {limitation}")
    st.markdown("- AI classifications are interpretations of public posts, even after the quality audit.")
    st.markdown("- Primary interviews or a survey are still required before any finding is treated as confirmed.")
    st.markdown("- Interviews are still needed to investigate what a person remembered before they formed a search.")
    st.markdown("- This interface does not recommend a product solution.")
    _how_ai_is_used()


def _record_panel(record: Dict[str, Any], key_prefix: str) -> None:
    st.markdown("---")
    left, right = st.columns(2)
    with left:
        st.markdown("##### What the person wrote")
        st.markdown(
            f"**Record:** {record['record_id']}  \n"
            f"**Source:** {record['source']}  \n"
            f"**Date:** {record['date']}  \n"
            f"**Relevance:** {record['relevance_label'] or 'Not recorded'}"
        )
        st.text_area(
            f"Verbatim text {record['record_id']}",
            value=record["original_text"],
            height=180,
            disabled=True,
            label_visibility="collapsed",
            key=f"{key_prefix}-text-{record['record_id']}",
        )
        _source_link(record["source_url"])
        if record["relevance_reason"]:
            st.caption(f"Relevance note: {record['relevance_reason']}")
    with right:
        st.markdown("##### Audited interpretation")
        st.caption("This is a research reading of the post. It is not a replacement for the wording on the left.")
        if not record["classified"]:
            st.info("This record was not automatically classified. Phase 2 left it Uncertain.")
        else:
            review = "Needs human review" if record["needs_human_review"] else "Not flagged for human review"
            st.markdown(
                f"**Failure stage:** {record['primary_failure_stage']}  \n"
                f"**Secondary stage:** {record['secondary_failure_stage']}  \n"
                f"**Outcome:** {record['retrieval_outcome']}  \n"
                f"**Evidence strength:** {record['evidence_strength']}  \n"
                f"**Confidence:** {record['confidence']}  \n"
                f"**Human review:** {review}"
            )
            if record["human_review_reason"]:
                st.caption(record["human_review_reason"])
            st.markdown(f"**Remembered clues:** {record['remembered_clues']}")
            st.markdown(f"**Forgotten clues:** {record['missing_or_forgotten_clues']}")
            st.markdown(f"**Search or browse behaviour:** {record['search_or_browse_behavior']}")
            st.markdown(f"**Reformulation:** {record['reformulation_behavior']}")
            st.markdown(f"**Manual browsing:** {record['manual_browsing_behavior']}")
            st.markdown(f"**Manual scroll signal:** {record['manual_scroll_signal']}")
            st.markdown(f"**Workaround:** {record['workaround']}")
            st.markdown(f"**Photo type:** {record['photo_type']}")
            with st.expander("Classification note"):
                st.write(record["failure_reason"] or "No failure reason was saved.")
                st.write(record["ai_interpretation"] or "No interpretation note was saved.")


def _open_buttons(record_ids: List[str], lookup: Dict[str, Dict[str, Any]], key_prefix: str) -> None:
    st.caption("Open a supporting record in the Evidence explorer.")
    columns = st.columns(min(4, max(len(record_ids), 1)))
    for index, record_id in enumerate(record_ids):
        if record_id not in lookup:
            st.error(f"{record_id} is not in the saved corpus.")
            continue
        if columns[index % len(columns)].button(record_id, key=f"open-{key_prefix}-{record_id}"):
            st.session_state["discovery_section"] = "Evidence explorer"
            st.session_state["disc_evidence_record"] = record_id
            st.session_state["disc_evidence_search"] = ""
            st.session_state["disc_evidence_source"] = "All sources"
            st.session_state["disc_evidence_label"] = "All relevance decisions"
            st.rerun()


def _apply_failure_filters(
    records: List[Dict[str, Any]],
    stage: str,
    source: str,
    photo: str,
    strength: str,
    outcome: str,
    review: str,
) -> List[Dict[str, Any]]:
    filtered = records
    filtered = _match(filtered, "primary_failure_stage", stage, "All stages")
    filtered = _match(filtered, "source", source, "All sources")
    filtered = _match(filtered, "photo_type", photo, "All photo types")
    filtered = _match(filtered, "evidence_strength", strength, "All strengths")
    filtered = _match(filtered, "retrieval_outcome", outcome, "All outcomes")
    if review == "Needs human review":
        filtered = [record for record in filtered if record["needs_human_review"]]
    elif review == "Not flagged":
        filtered = [record for record in filtered if not record["needs_human_review"]]
    return filtered


def _match(records: List[Dict[str, Any]], field: str, selected: str, all_label: str) -> List[Dict[str, Any]]:
    if selected == all_label:
        return records
    return [record for record in records if str(record[field]) == selected]


def _options(records: List[Dict[str, Any]], field: str, all_label: str) -> List[str]:
    values = sorted({str(record[field]) for record in records if str(record[field]).strip()})
    if field == "primary_failure_stage":
        values = sorted(values, key=lambda value: value if value.startswith("F") else f"Z{value}")
    return [all_label] + values


def _failure_table(records: List[Dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "record_id": record["record_id"],
            "source": record["source"],
            "failure_stage": record["primary_failure_stage"],
            "photo_type": record["photo_type"],
            "outcome": record["retrieval_outcome"],
            "evidence_strength": record["evidence_strength"],
            "human_review": "Needs review" if record["needs_human_review"] else "Not flagged",
        }
        for record in records
    ])


def _evidence_table(records: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for record in records:
        text = " ".join(record["original_text"].split())
        if len(text) > 140:
            text = text[:140].rsplit(" ", 1)[0] + "…"
        rows.append({
            "record_id": record["record_id"],
            "source": record["source"],
            "date": record["date"],
            "relevance": record["relevance_label"],
            "failure_stage": record["primary_failure_stage"] if record["classified"] else "Not classified",
            "original_text": text,
        })
    return pd.DataFrame(rows)


def _stage_frame(analysis: Dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "failure_stage": stage["failure_stage"],
            "records": stage["record_count"],
            "share": stage["share"]["display"],
            "human_review": stage["human_review_count"],
        }
        for stage in analysis["failure_stages"]
    ])


def _count_frame(counts: Dict[str, int], label: str, value_name: str) -> pd.DataFrame:
    return pd.DataFrame([{label: key, value_name: value} for key, value in counts.items()])


def _format_mix(mix: Dict[str, int]) -> str:
    if not mix:
        return "None"
    return "; ".join(f"{key}: {value}" for key, value in mix.items())


def _field_text(record: Dict[str, Any], field: str) -> str:
    if not field:
        return ""
    value = record.get(field, "")
    if isinstance(value, bool):
        return "Needs human review" if value else "Not flagged"
    return str(value)


def _source_link(url: str) -> None:
    if str(url).startswith("http://") or str(url).startswith("https://"):
        st.markdown(f"[Open source URL]({url})")
    elif url:
        st.markdown(f"**Source URL:** `{url}`")
