import sys, os
sys.path.insert(0, os.path.abspath("."))
from dotenv import load_dotenv
load_dotenv()
from brain_options.store.db import OptionsDatabase

db = OptionsDatabase(os.getenv("DATABASE_URL"))
with db._get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT alpha_id, archetype, sharpe, fitness, margin, turnover, status FROM options_alphas WHERE alpha_id = '0mX0kG86'")
        print("0mX0kG86 row:", cur.fetchone())
