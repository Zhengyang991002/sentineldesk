"""Shared paths and tunable constants. Tune thresholds on the VAL split only, never on test."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_CSV = DATA_DIR / "raw" / "tickets.csv"
KB_PARQUET = DATA_DIR / "kb.parquet"            # 80% split; column `split` in {"fit", "val"}
TEST_INPUTS = DATA_DIR / "test_inputs.parquet"  # ticket_id, subject, body ONLY
TEST_LABELS = DATA_DIR / "test_labels.parquet"  # ticket_id, type, queue, priority, language (scoring only)
ARTIFACTS = ROOT / "artifacts"
REPORTS = ROOT / "reports"

DATASET_URL = (
    "https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets/resolve/main/"
    "aa_dataset-tickets-multi-lang-5-2-50-version.csv"
)
SEED = 42
VAL_FRAC = 0.10  # fraction of the KB split held out for threshold tuning

# Escalation gate thresholds (tune on val only)
TAU_CONF = 0.50  # reporting only (scripts/eval_by_language.py); confidence no longer escalates on its own
TAU_SIM = 0.50   # min cosine similarity for a resolved precedent to count as "similar" (embedding backend).
                 # Val p1=0.75, out-of-scope max=0.39, short live queries ~0.58-0.72 (scripts/tune_sim.py)
TOP_K = 5

# LLM
LLM_MODEL = "claude-opus-5-5"
LLM_MAX_TOKENS = 1500
