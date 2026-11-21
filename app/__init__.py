"""SentinelDesk API (FastAPI). Run from the repo root: uvicorn app.main:app --port 8000"""
import logging

try:  # read .env (GOOGLE_CLOUD_PROJECT, PIPELINE_MODE, ...) before any module reads the environment
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
