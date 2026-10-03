"""
RecallScope — Relevance Filtering Module
Phase 2: Relevance Filtering

Evaluates raw public evidence records against the core research question:
"Where and why do users struggle when trying to retrieve a photo they remember exists,
especially when they cannot precisely describe or locate it?"

Preserves raw evidence strictly read-only and writes processed relevance
decisions with explainability fields to data/public_evidence_relevance.csv.
"""

from pathlib import Path
from typing import Dict, Any, Tuple
import warnings

# Suppress optional binary warnings from older conda C-extensions
warnings.filterwarnings("ignore", category=Warning)

import pandas as pd

# Grounded relevance mapping for the 24-record interim corpus
# Each entry is strictly grounded in the verbatim text of the record
RELEVANCE_DATA = {
    "REC_001": {
        "relevance_label": "Relevant",
        "relevance_reason": "User searches for a specific remembered photo (Grandma's cat), fails with search parameters, and is forced to manually scroll through years of photos.",
        "evidence_excerpt": "I wanted to find this photo the other day, and no amount of search parameters found it.",
        "review_required": False
    },
    "REC_002": {
        "relevance_label": "Relevant",
        "relevance_reason": "User describes the friction of needing to remember the exact capture date and manually scrolling back through history to find a photo.",
        "evidence_excerpt": "If I want to find a photo of something and show it to someone, I have to remember the date I took it and scroll back through the history",
        "review_required": False
    },
    "REC_003": {
        "relevance_label": "Relevant",
        "relevance_reason": "User is searching for an older photo of a remembered distinct item in a large collection without remembering the date.",
        "evidence_excerpt": "I am trying to find an older photo I have of that same item but I have so many photos I can't find it and I don't remember when I took the photo.",
        "review_required": False
    },
    "REC_004": {
        "relevance_label": "Relevant",
        "relevance_reason": "User experiences difficulty locating specific photos within a large album containing over 1400 images.",
        "evidence_excerpt": "I can't easily find the pics I need to move around, not when I'm looking thru 1400 pics.",
        "review_required": False
    },
    "REC_005": {
        "relevance_label": "Relevant",
        "relevance_reason": "Keyword search for 'bike' returns irrelevant candidate photos unrelated to the search term.",
        "evidence_excerpt": "Search results are now giving me photos that have nothing to do with the search term.",
        "review_required": False
    },
    "REC_006": {
        "relevance_label": "Relevant",
        "relevance_reason": "Keyword search for 'dog' surfaces only a tiny fraction of existing photos, leaving candidate retrieval incomplete.",
        "evidence_excerpt": "When I search for 'dog', only 6 pictures come up even though I am SURE I have more dog photos.",
        "review_required": False
    },
    "REC_007": {
        "relevance_label": "Relevant",
        "relevance_reason": "User is seeking ways to search for specific photos and videos after previously used keyword renaming ceased working.",
        "evidence_excerpt": "Does anyone have a way to search for specific photos and or videos?",
        "review_required": False
    },
    "REC_008": {
        "relevance_label": "Relevant",
        "relevance_reason": "User reports breakdown in finding specific older photos using search keywords that formerly pinpointed items.",
        "evidence_excerpt": "finding specific photos from years gone by, thanks to the search function being so pinpoint using the littlest of terms.",
        "review_required": False
    },
    "REC_009": {
        "relevance_label": "Relevant",
        "relevance_reason": "User executes a basic keyword search for a photo and the system returns zero results ('not found').",
        "evidence_excerpt": "I will type in the most basic thing to search for a photo and it said not found.",
        "review_required": False
    },
    "REC_010": {
        "relevance_label": "Relevant",
        "relevance_reason": "User experiences browsing and scrolling failure while looking for an older photo due to the interface reloading and resetting position.",
        "evidence_excerpt": "makes me lose my place when I'm looking for something.",
        "review_required": False
    },
    "REC_011": {
        "relevance_label": "Relevant",
        "relevance_reason": "Inability to retrieve remembered photos in a massive library (500k+ photos) using keyword search ('Sunfish') where manual scrolling is impossible.",
        "evidence_excerpt": "Search for 'Sunfish' found nothing even though I have hundreds of close-up photos.",
        "review_required": False
    },
    "REC_012": {
        "relevance_label": "Relevant",
        "relevance_reason": "User describes query reformulation struggle ('yellow truck' vs 'pickup truck') with inconsistent and unstable candidate results.",
        "evidence_excerpt": "I'll try different phrasing like 'pickup truck' and it'll add a few more trucks but also lose some of the yellow trucks it initially found.",
        "review_required": False
    },
    "REC_013": {
        "relevance_label": "Relevant",
        "relevance_reason": "User experiences both candidate gap (tiny subset of dog photos) and candidate mismatch (blowtorch query returns 8 items with no blowtorch).",
        "evidence_excerpt": "Now when I search for 'dog' I get a tiny subset of the photos I used to.",
        "review_required": False
    },
    "REC_014": {
        "relevance_label": "Relevant",
        "relevance_reason": "Keyword search brings up screenshots of text rather than intended visual photos, forcing manual finding as fallback.",
        "evidence_excerpt": "I can still find the photo manually, but not with any keywords that formerly worked.",
        "review_required": False
    },
    "REC_015": {
        "relevance_label": "Uncertain",
        "relevance_reason": "Mixes missing folder files with search query attempts ('type 2020'); unclear whether photos disappeared due to sync/folder loss or search indexing failure.",
        "evidence_excerpt": "Around 5 of these missing photos show up if I type 2020 but none of the others.",
        "review_required": True
    },
    "REC_016": {
        "relevance_label": "Relevant",
        "relevance_reason": "User seeks to retrieve a specific remembered experience ('train museum visit') using search rather than scrolling through everything.",
        "evidence_excerpt": "I am looking to search a specific photo like train museum visit. It will make it easier for me to find the pic I am looking for instead of scrolling thru all.",
        "review_required": False
    },
    "REC_017": {
        "relevance_label": "Relevant",
        "relevance_reason": "User attempts to find a specific photo using exact filename clue, but searches return broad date-based candidates instead.",
        "evidence_excerpt": "I'm trying to find a photo by its exact filename. I tried several options but had no luck",
        "review_required": False
    },
    "REC_018": {
        "relevance_label": "Relevant",
        "relevance_reason": "User searches using a temporal clue ('today's date') to find recently uploaded photos, but candidate retrieval returns photos from ten years ago.",
        "evidence_excerpt": "I type today's date in the search and I bizarrely get random pictures from almost ten years ago.",
        "review_required": False
    },
    "REC_019": {
        "relevance_label": "Relevant",
        "relevance_reason": "User searches for a video using a previously tagged info phrase; search fails to locate it, forcing long manual digging.",
        "evidence_excerpt": "When I use the exact phrase, Photos isn't able to locate anything. Eventually I'm able to locate it by digging for a long time.",
        "review_required": False
    },
    "REC_020": {
        "relevance_label": "Relevant",
        "relevance_reason": "Archetypal vague memory retrieval: user recalls only visual context ('yellow sticky note') and system returns zero results for a photo known to exist.",
        "evidence_excerpt": "the only thing I could remember was that it was a yellow sticky note, I could search those words and the picture would pop right up. Now it usually tells me that it can't find anything",
        "review_required": False
    },
    "REC_021": {
        "relevance_label": "Relevant",
        "relevance_reason": "User expresses difficulty searching for a specific photo within a large list, though the statement is very brief and borderline.",
        "evidence_excerpt": "It is very difficult to search specific photo in a very long list.",
        "review_required": True
    },
    "REC_022": {
        "relevance_label": "Relevant",
        "relevance_reason": "User experiences post-retrieval browsing friction: after locating an initial photo, finding surrounding event photos requires manual timeline scrolling through tens of thousands of images.",
        "evidence_excerpt": "Once I find a photo that I was looking for, I usually want to browse other photos from that same event.",
        "review_required": False
    },
    "REC_023": {
        "relevance_label": "Uncertain",
        "relevance_reason": "Mixes keyword search behavior with multi-device backup status; unclear whether new phone photos are unbacked/unsynced or failing search indexing.",
        "evidence_excerpt": "When I search for keywords in the Google Photos app or on the web, I only get results from photos backed up from an old phone",
        "review_required": True
    },
    "REC_024": {
        "relevance_label": "Relevant",
        "relevance_reason": "User searches using remembered words from added descriptions, but photos fail to appear in search candidate results.",
        "evidence_excerpt": "when I try to search using the words from those descriptions, the photos do not appear in the search results.",
        "review_required": False
    }
}


def run_relevance_pipeline(raw_csv_path: str = None, output_csv_path: str = None) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Execute the Phase 2 relevance filtering pipeline.
    Reads data/public_evidence_raw.csv (read-only) and produces data/public_evidence_relevance.csv.

    Returns:
        (df_relevance, metrics_dict)
    """
    base_dir = Path(__file__).resolve().parent.parent.parent
    if raw_csv_path is None:
        raw_csv_path = base_dir / "data" / "public_evidence_raw.csv"
    else:
        raw_csv_path = Path(raw_csv_path)

    if output_csv_path is None:
        output_csv_path = base_dir / "data" / "public_evidence_relevance.csv"
    else:
        output_csv_path = Path(output_csv_path)

    if not raw_csv_path.exists():
        raise FileNotFoundError(f"Raw evidence file not found at: {raw_csv_path}")

    # Read raw evidence strictly read-only
    df_raw = pd.read_csv(raw_csv_path, encoding="utf-8", dtype=str)

    # Build relevance dataframe preserving all original fields
    rows = []
    uncertain_records = []

    for _, row in df_raw.iterrows():
        rec_id = str(row["record_id"])
        original_text = str(row["original_text"])

        meta = RELEVANCE_DATA.get(rec_id, {
            "relevance_label": "Uncertain",
            "relevance_reason": "No explicit classification entry found; defaulted to Uncertain.",
            "evidence_excerpt": original_text[:50],
            "review_required": True
        })

        relevance_label = meta["relevance_label"]
        relevance_reason = meta["relevance_reason"]
        evidence_excerpt = meta["evidence_excerpt"]
        review_required = bool(meta.get("review_required", relevance_label == "Uncertain"))

        # Verify excerpt is a true substring of original_text
        if evidence_excerpt not in original_text:
            raise ValueError(
                f"Integrity check failed for {rec_id}: evidence_excerpt '{evidence_excerpt}' "
                f"is not a verbatim substring of original_text!"
            )

        if relevance_label not in ["Relevant", "Irrelevant", "Uncertain"]:
            raise ValueError(
                f"Invalid relevance_label '{relevance_label}' for {rec_id}. "
                f"Must be one of ['Relevant', 'Irrelevant', 'Uncertain']."
            )

        # Enforce review_required = True for all Uncertain records
        if relevance_label == "Uncertain":
            review_required = True

        out_row = {
            "record_id": rec_id,
            "source": row["source"],
            "date": row["date"],
            "original_text": original_text,
            "source_url": row["source_url"],
            "relevance_label": relevance_label,
            "relevance_reason": relevance_reason,
            "evidence_excerpt": evidence_excerpt,
            "review_required": review_required
        }
        rows.append(out_row)

        if relevance_label == "Uncertain":
            uncertain_records.append({
                "record_id": rec_id,
                "relevance_reason": relevance_reason,
                "evidence_excerpt": evidence_excerpt,
                "source": row["source"]
            })

    df_relevance = pd.DataFrame(rows)

    # Save to data/public_evidence_relevance.csv
    df_relevance.to_csv(output_csv_path, index=False, encoding="utf-8")

    # Calculate metrics
    total_records = len(df_relevance)
    relevant_count = int((df_relevance["relevance_label"] == "Relevant").sum())
    irrelevant_count = int((df_relevance["relevance_label"] == "Irrelevant").sum())
    uncertain_count = int((df_relevance["relevance_label"] == "Uncertain").sum())
    review_required_count = int(df_relevance["review_required"].sum())
    relevance_rate = (relevant_count / total_records * 100.0) if total_records > 0 else 0.0

    metrics = {
        "total_records": total_records,
        "relevant_count": relevant_count,
        "irrelevant_count": irrelevant_count,
        "uncertain_count": uncertain_count,
        "review_required_count": review_required_count,
        "relevance_rate": relevance_rate,
        "uncertain_records": uncertain_records,
        "output_csv_path": str(output_csv_path)
    }

    return df_relevance, metrics


def load_relevance_dataset() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Safely load the processed relevance dataset.
    If the relevance file does not exist, runs the pipeline to generate it.
    """
    base_dir = Path(__file__).resolve().parent.parent.parent
    relevance_csv = base_dir / "data" / "public_evidence_relevance.csv"

    if not relevance_csv.exists():
        return run_relevance_pipeline()

    df = pd.read_csv(relevance_csv, encoding="utf-8", dtype={"review_required": bool})
    # Ensure boolean conversion
    df["review_required"] = df["review_required"].astype(bool)

    total_records = len(df)
    relevant_count = int((df["relevance_label"] == "Relevant").sum())
    irrelevant_count = int((df["relevance_label"] == "Irrelevant").sum())
    uncertain_count = int((df["relevance_label"] == "Uncertain").sum())
    review_required_count = int(df["review_required"].sum())
    relevance_rate = (relevant_count / total_records * 100.0) if total_records > 0 else 0.0

    uncertain_records = []
    for _, row in df[df["relevance_label"] == "Uncertain"].iterrows():
        uncertain_records.append({
            "record_id": row["record_id"],
            "relevance_reason": row["relevance_reason"],
            "evidence_excerpt": row["evidence_excerpt"],
            "source": row["source"]
        })

    metrics = {
        "total_records": total_records,
        "relevant_count": relevant_count,
        "irrelevant_count": irrelevant_count,
        "uncertain_count": uncertain_count,
        "review_required_count": review_required_count,
        "relevance_rate": relevance_rate,
        "uncertain_records": uncertain_records,
        "output_csv_path": str(relevance_csv)
    }

    return df, metrics
