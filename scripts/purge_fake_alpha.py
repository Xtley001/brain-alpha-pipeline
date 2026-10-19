import sys
sys.path.insert(0, '.')
import brain_options.core.dns_fallback
import psycopg
from brain_options.config import OptionsConfig

cfg = OptionsConfig.from_env()
with psycopg.connect(cfg.database_url, autocommit=True) as conn:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM options_alphas WHERE alpha_id = '88v19LqG'")
        print(f"Purged 88v19LqG from options_alphas. Rows affected: {cur.rowcount}")
