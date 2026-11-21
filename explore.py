import io
import pandas as pd
import pyarrow.parquet as pq
from src import config
from src.data import build_text, load_kb

kb = load_kb()
kb["text"] = [build_text(s, b) for s, b in zip(kb["subject"], kb["body"])]
ti = pd.read_parquet(config.TEST_INPUTS, columns=["subject", "body"])
test_text = pd.Series([build_text(s, b) for s, b in zip(ti["subject"], ti["body"])])
test_rows = pq.ParquetFile(config.TEST_INPUTS).metadata.num_rows
out = io.StringIO()

def p(*a):
    print(*a)
    print(*a, file=out)

def vc(col):
    s = kb[col].fillna("<NA>").value_counts()
    return pd.DataFrame({"count": s, "pct": (100 * s / len(kb)).round(2)})

def empty(col):
    return int((kb[col].isna() | (kb[col].astype(str).str.strip() == "")).sum())

p("# EDA (KB only: data/kb.parquet)\n")
p(f"KB rows: {len(kb)}")
p(f"test rows: {test_rows}\n")
p("## Columns\n")
p(kb.dtypes.to_string(), "\n")
for c in ["type", "queue", "priority", "language"]:
    p(f"## {c}\n")
    p(vc(c).to_string(), "\n")
p("## type x priority\n")
p(pd.crosstab(kb["type"].fillna("<NA>"), kb["priority"].fillna("<NA>")).to_string(), "\n")
p("## Null or empty\n")
for c in ["subject", "body", "answer"]:
    p(f"{c}: {empty(c)}")
bl = kb["body"].fillna("").str.len()
p("\n## Body length (chars)\n")
p(f"mean: {bl.mean():.1f}  median: {bl.median():.0f}  p95: {bl.quantile(0.95):.0f}")
p("\n## Duplicates\n")
p(f"exact duplicate texts in KB: {int(kb['text'].duplicated().sum())}")
p(f"test texts also in KB: {int(test_text.isin(set(kb['text'])).sum())}")
open("data/EDA.md", "w", encoding="utf-8").write(out.getvalue())
