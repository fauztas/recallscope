"""
Temporary Phase 2 pipeline runner — used for validation only.
Do not call this from Streamlit.
"""
from app.utils.relevance_filter import run_relevance_pipeline

df, m = run_relevance_pipeline()

print(f"Total records   : {m['total_records']}")
print(f"Relevant        : {m['relevant_count']}")
print(f"Irrelevant      : {m['irrelevant_count']}")
print(f"Uncertain       : {m['uncertain_count']}")
print(f"Review Required : {m['review_required_count']}")
print(f"Relevance Rate  : {m['relevance_rate']:.1f}%")
print(f"Output CSV      : {m['output_csv_path']}")
print("\nUncertain records:")
for r in m["uncertain_records"]:
    print(f"  {r['record_id']} — {r['relevance_reason'][:80]}")
