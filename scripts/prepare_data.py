"""Download the CSV, apply the official split, write parquet files, print a quick EDA.

Run from the repo root:  python -m scripts.prepare_data
Leakage rule: the test split's `answer` column is dropped here and never written to disk.
"""
import pandas as pd

from src import config
from src.data import LABELS, download_if_missing, official_split


def main() -> None:
    download_if_missing()
    df = pd.read_csv(config.RAW_CSV)
    print(f"rows={len(df)}  columns={list(df.columns)}")

    kb, test = official_split(df)

    val_idx = kb.sample(frac=config.VAL_FRAC, random_state=config.SEED).index
    kb["split"] = "fit"
    kb.loc[val_idx, "split"] = "val"

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    kb.to_parquet(config.KB_PARQUET, index=False)
    test[["ticket_id", "subject", "body"]].to_parquet(config.TEST_INPUTS, index=False)
    test[["ticket_id"] + LABELS + ["language"]].to_parquet(config.TEST_LABELS, index=False)

    assert set(kb["ticket_id"]).isdisjoint(test["ticket_id"]), "KB/test overlap!"
    print(f"kb={len(kb)} (fit={int((kb.split == 'fit').sum())}, val={int((kb.split == 'val').sum())})"
          f"  test={len(test)}")

    print("\n--- EDA (KB only) ---")
    print("null/empty subject:", int(kb["subject"].isna().sum() + (kb["subject"].astype(str).str.strip() == "").sum()))
    print("null body:", int(kb["body"].isna().sum()), " null answer:", int(kb["answer"].isna().sum()))
    for col in ["language"] + LABELS:
        print(f"\n{col}:\n{kb[col].value_counts(dropna=False).to_string()}")
    hp = ((kb["priority"] == "high") & (kb["type"] == "Incident")).mean()
    print(f"\nhigh-priority Incident share: {hp:.1%}")


if __name__ == "__main__":
    main()
