"""
RecallScope — Primary research view

Observed interviews stay separate from the public-evidence corpus.
Opening this page does not call Groq.
"""

from typing import Any, Dict, List

import streamlit as st

from app.utils.discovery_data import load_research_analysis
from app.utils.primary_research import category_counts, load_primary_research, sessions_where


def render_primary_research() -> None:
    try:
        payload = load_primary_research()
    except (OSError, ValueError, KeyError) as exc:
        st.error("The primary-research file could not be read. No interview finding was invented.")
        st.caption(str(exc))
        return

    participants = payload["participants"]
    session_count = len(participants)
    st.title("Primary research")
    st.subheader(f"Observed retrieval sessions — n={session_count}")
    st.warning(payload["sample_banner"])
    st.write(payload["method_statement"])
    st.caption(payload["separation_note"])
    st.write(payload["research_question"])

    st.markdown("### What users remembered vs what they searched")
    st.caption(payload["expression_rule"])
    for person in participants:
        _comparison(person)

    st.markdown("### Cautious memory-clue coding")
    st.caption("A category is counted when the session states that kind of clue. Hedged wording stays inside the count and is marked. These are not claims about Google Photos users generally.")
    _categories(payload, session_count)

    st.markdown("### Observed retrieval behaviour")
    st.caption("Only behaviours recorded in the session are counted. A large result set is not treated as a recognition failure.")
    _behaviours(payload, session_count)

    st.markdown("### Failure-journey reading")
    st.caption(payload["recognition_rule"])
    st.caption(payload["indexing_rule"])
    st.caption("More than one stage can be relevant in the same session. Unknown stays available.")
    for person in participants:
        _journey(person)

    st.markdown("### Cross-interview observations")
    st.caption("Each observation below is limited to these five sessions.")
    for observation in payload["observations"]:
        _observation(observation, participants)

    st.markdown("### What remains ambiguous")
    for point in payload["ambiguous_points"]:
        st.markdown(f"- {point}")

    st.markdown("### What these interviews cannot tell us")
    for limitation in payload["limitations"]:
        st.markdown(f"- {limitation}")

    st.markdown("### How this complements public evidence")
    _triangulation(payload)

    st.markdown("### What this page does not do")
    st.markdown(
        """
- It does not mix these interviews into the public-evidence counts.
- It does not send interviews to Ask the Evidence.
- It does not select a product solution, a target segment, or a final root cause.
- It does not treat one stage as the main cause.
        """
    )


def _comparison(person: Dict[str, Any]) -> None:
    st.markdown(f"#### {person['participant_id']} — {person['name']}")
    st.caption(
        f"Age {person['age']} · {person['gender']} · {person['occupation']} · "
        f"Final outcome: {person['outcome']}. An unrecorded ending is not a failed retrieval."
    )
    st.write(f"Retrieval target: {person['retrieval_target']}")
    if person.get("target_label_note"):
        st.caption(person["target_label_note"])

    remembered, searched = st.columns(2)
    with remembered:
        st.markdown("**What they remembered before searching**")
        st.text_area(
            f"Unaided memory {person['participant_id']}",
            value=person["unaided_memory"],
            height=220,
            disabled=True,
            label_visibility="collapsed",
            key=f"memory-{person['participant_id']}",
        )
    with searched:
        st.markdown("**What they actually searched**")
        for step in person["search_sequence"]:
            query = step["query"] or step["action"]
            st.markdown(f"{step['order']}. **{query}**")
            st.caption(step["action"])
            if step.get("reaction"):
                st.write(f"\"{step['reaction']}\"")

    typed = [clue for clue in person["remembered_clues"] if clue.get("in_typed_query")]
    omitted = [clue for clue in person["remembered_clues"] if not clue.get("in_typed_query")]
    st.markdown(
        f"**Coded clues in a typed query:** {len(typed)} of {len(person['remembered_clues'])} listed clues. "
        f"**Not in a typed query:** {len(omitted)} of {len(person['remembered_clues'])}."
    )
    left, right = st.columns(2)
    with left:
        st.markdown("**Remembered information expressed in a typed search**")
        for clue in typed:
            st.markdown(f"- {_clue_label(clue)}")
        if not typed:
            st.caption("None of the listed clues were typed.")
    with right:
        st.markdown("**Remembered information not expressed in a typed search**")
        for clue in omitted:
            st.markdown(f"- {_clue_label(clue)}")
            if clue.get("expression_note"):
                st.caption(clue["expression_note"])
    st.markdown("**What happened after the first search**")
    st.write(person["after_first_search"])
    st.markdown("**Fallback or workaround**")
    st.write(person["fallback"])
    if person.get("memory_during_search"):
        st.caption(f"Said during the search: \"{person['memory_during_search']}\"")
    st.markdown("**What they described as hardest**")
    st.write(person["hardest_part"])
    st.caption(person["outcome_note"])
    st.divider()


def _clue_label(clue: Dict[str, Any]) -> str:
    hedge = " (hedged)" if clue.get("certainty") == "hedged" else ""
    return f"{clue['text']}{hedge}"


def _categories(payload: Dict[str, Any], session_count: int) -> None:
    for row in category_counts(payload):
        ids = ", ".join(row["participant_ids"]) or "none"
        hedged = ", ".join(row["hedged_participant_ids"]) or "none"
        st.markdown(f"**{row['category']}** — {row['count']} of {session_count} observed sessions")
        st.caption(f"Sessions: {ids}. Sessions where this category was hedged: {hedged}.")


def _behaviours(payload: Dict[str, Any], session_count: int) -> None:
    rows = [
        ("Broad first search", "broad_first_search", True, "The first typed query was a short general term."),
        ("Query reformulation", "query_reformulation", True, "At least one later typed query was recorded."),
        ("Participant-reported large result set", "reported_large_result_set", True, "The participant described the results as numerous. This is not a recognition code."),
        ("Relevant-but-broad results described", "relevant_but_broad_results", True, "The participant described results in the broad category of the words, rather than the remembered situation. Omar did not describe the contents."),
        ("Approximate date or year fallback", "approximate_time_fallback", True, "A date or year attempt was recorded after keyword search."),
        ("Result mismatch described by the participant", "described_result_mismatch", True, "The participant said the results were a different kind of item from the remembered situation."),
        ("Remembered detail left out of typed queries", "remembered_detail_not_typed", True, "At least one stated clue was not in a typed query."),
        ("Recognition Gap shown", "recognition_gap_shown", True, "The target was on screen and hard to identify. The expected count here is 0 of 5."),
    ]
    for label, flag, expected, meaning in rows:
        ids = sessions_where(payload, flag, expected)
        st.markdown(f"**{label}** — {len(ids)} of {session_count} observed sessions")
        st.caption(meaning)
        st.caption("Sessions: " + (", ".join(ids) or "none") + ".")

    st.markdown("**People or trip route**")
    for state, meaning in (
        ("attempted", "A people or trip route was attempted."),
        ("considered", "A people or trip route was mentioned, but not recorded as completed."),
        ("not observed", "No people or trip route was recorded."),
    ):
        ids = sessions_where(payload, "people_or_trip_route", state)
        st.caption(f"{meaning} {len(ids)} of {session_count}: {', '.join(ids) or 'none'}.")

    st.markdown("**Manual browsing**")
    for state, meaning in (
        ("observed", "Manual browsing was recorded."),
        ("anticipated", "Scrolling was described as likely or necessary. A completed browse was not recorded."),
    ):
        ids = sessions_where(payload, "manual_browsing", state)
        st.caption(f"{meaning} {len(ids)} of {session_count}: {', '.join(ids) or 'none'}.")
    st.caption("Zainab's manual-browsing step has no separate spoken quote. Sara spoke while the session recorded browsing.")


def _journey(person: Dict[str, Any]) -> None:
    with st.expander(f"{person['participant_id']} — {person['name']} — retrieval journey"):
        for stage in person["journey"]:
            st.markdown(f"**{stage['stage']}** — {stage['reading']}")
            st.write(stage["note"])


def _observation(observation: Dict[str, Any], participants: List[Dict[str, Any]]) -> None:
    names = {person["participant_id"]: person["name"] for person in participants}
    ids = observation["participant_ids"]
    st.markdown(f"**{observation['observation']}**")
    st.caption("Confidence: " + observation["confidence"])
    if ids:
        labelled = ", ".join(f"{participant_id} ({names.get(participant_id, '')})" for participant_id in ids)
        st.caption("Supporting sessions: " + labelled)
    else:
        st.caption("Supporting sessions: none. The rule was not met in these five sessions.")
    for item in observation.get("evidence", []):
        st.write(f"{item['participant_id']}: \"{item['quote']}\"")
    st.markdown("**What the evidence supports**")
    st.write(observation["supports"])
    st.markdown("**What it does not establish**")
    st.write(observation["does_not_establish"])


def _triangulation(payload: Dict[str, Any]) -> None:
    st.write(
        "Public evidence shows naturally occurring complaints and workarounds from public posts. "
        "These interviews show what five participants remembered before they searched, and what they did during one observed attempt. "
        "The counts are not added together."
    )
    try:
        analysis = load_research_analysis()
    except (OSError, ValueError, KeyError):
        st.caption("The saved public-evidence analysis could not be read. Interview counts above are unchanged.")
        return

    stages = {item.get("failure_stage"): item for item in analysis.get("failure_stages", [])}
    f5 = stages.get("F5 — Recognition Gap", {})
    f8 = stages.get("F8 — Unknown / Insufficient Evidence", {})
    scroll = next(
        (item for item in analysis.get("cross_patterns", []) if "manual-scroll signal" in item.get("question", "")),
        {},
    )
    classified_count = analysis.get("input", {}).get("classified_record_count")
    st.markdown("**Public-evidence counts, kept in their own corpus**")
    st.caption(analysis.get("disclaimer", ""))
    columns = st.columns(3)
    columns[0].metric("Classified public records", classified_count if classified_count is not None else "Unread")
    columns[1].metric("Public F5 — Recognition Gap", f5.get("share", {}).get("display", "Unread"))
    columns[2].metric("Public F8 — Unknown", f8.get("share", {}).get("display", "Unread"))
    if scroll:
        st.caption(
            "Public records with manual_scroll_signal Yes: "
            + scroll.get("share", {}).get("display", "")
            + ". Record IDs: "
            + ", ".join(scroll.get("supporting_record_ids", []))
            + "."
        )
    st.markdown("**What can be read across the two sources**")
    st.markdown(
        """
- The interviews supply a before-search account. The public posts often do not, which is one reason many public records stay at an unknown stage.
- Public posts include people describing a search that did not yield the wanted photo, and people describing many results or scrolling. The interviews record attempts, reactions, and later strategies. They do not systematically record whether the target was found, so they are not counted as failed retrievals. The counts stay separate.
- These five sessions do not show a Recognition Gap. The public corpus still has its own recognition record. The interview result does not remove that record, and the public record does not prove recognition was the problem in these sessions.
- Public scrolling counts and the interview browsing counts use different denominators. They are not one workaround rate.
        """
    )
    st.caption(
        f"Interview sample size remains n={len(payload['participants'])}. "
        "Neither source, and not the two together, establishes population prevalence."
    )
