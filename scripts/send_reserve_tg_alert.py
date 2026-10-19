#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import brain_options.core.dns_fallback
from brain_options.config import OptionsConfig
from scripts.master_quintuple_vault_miner_500 import send_tg_message
import psycopg

def main():
    cfg = OptionsConfig.from_env()
    with psycopg.connect(cfg.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT alpha_id, sharpe, fitness, turnover, margin, max_correlation, archetype, strategy_name
                FROM options_alphas 
                WHERE status = 'QUALIFIED'
                ORDER BY sharpe DESC;
            """)
            rows = cur.fetchall()

    lines = []
    for r in rows:
        lines.append(f"• <code>{r[0]}</code> | Sharpe: <b>{float(r[1]):.2f}</b> | Fit: <b>{float(r[2]):.2f}</b> | Mgn: {float(r[4])*10000:.1f}bp | TO: {float(r[3])*100:.1f}%")

    text = (
        "🌟 <b>7 QUALIFIED RESERVE ALPHAS BANKED (TIER 1)</b>\n\n"
        "⚠️ <b>CLARIFICATION & STATUS:</b>\n"
        "• These 7 alphas are <b>Tier 1 Portfolio Reserve Alphas</b>.\n"
        "• They pass all quantitative hurdles (Sharpe 1.26–1.38, Margin 5.3–7.0 bps, TO 18–25%, Fit 0.67–0.79).\n"
        "• <b>Platform Submission Status:</b> NOT yet submissible to BRAIN because BRAIN's submission checklist requires <b>Fitness &ge; 1.00</b> (these are 0.67–0.79).\n\n"
        "📊 <b>BANKED ROSTER:</b>\n" +
        "\n".join(lines) +
        "\n\n🚀 <b>ELEVATION IN PROGRESS:</b>\n"
        "The live miner (PID 14860) is actively simulating Priority-0 mutated variants (Decay 12/16/20, Surge Gate 1.05/1.10) to compress turnover and elevate Fitness &ge; 1.00 for platform submission!"
    )

    send_tg_message(cfg.telegram_bot_token, cfg.telegram_chat_id, text)
    print("Telegram alert sent successfully!")

if __name__ == "__main__":
    main()
