"""Data loading and the official 80/20 split. Owner: integrator."""
import urllib.request

import pandas as pd

from src import config

LABELS = ["type", "queue", "priority"]


def build_text(subject, body) -> str:
    """Join subject and body; tolerate None/NaN/empty subject or body."""
    parts = []
    for part in (subject, body):
        if part is None or (isinstance(part, float) and pd.isna(part)):
            continue
        part = str(part).strip()
        if part:
            parts.append(part)
    return "\n".join(parts)


def download_if_missing() -> None:
    if config.RAW_CSV.exists():
        return
    config.RAW_CSV.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading dataset to {config.RAW_CSV} ...")
    urllib.request.urlretrieve(config.DATASET_URL, config.RAW_CSV)


def official_split(df: pd.DataFrame):
    """Exactly the challenge's snippet: shuffle(seed 42), TKT ids, first 80% = KB, rest = test."""
    df = df.sample(frac=1.0, random_state=config.SEED).reset_index(drop=True)
    df["ticket_id"] = [f"TKT-{i:05d}" for i in range(len(df))]
    split_idx = int(len(df) * 0.8)
    return df.iloc[:split_idx].copy(), df.iloc[split_idx:].copy()


def load_kb(part: str | None = None) -> pd.DataFrame:
    """part=None -> whole KB; "fit" -> training/index part; "val" -> tuning part."""
    kb = pd.read_parquet(config.KB_PARQUET)
    return kb if part is None else kb[kb["split"] == part].reset_index(drop=True)


def load_test_inputs() -> pd.DataFrame:
    return pd.read_parquet(config.TEST_INPUTS)


def load_test_labels() -> pd.DataFrame:
    return pd.read_parquet(config.TEST_LABELS)
