import pypdf

# 1. Xing Zhang Zhao: Page 7-9
reader_xzz = pypdf.PdfReader("docs/research/Xing_Zhang_Zhao_Volatility_Smirk.pdf")
print("=== XING ZHANG ZHAO PAGES 7-10 ===")
for p in range(6, 10):
    text = reader_xzz.pages[p].extract_text()
    print(f"--- PAGE {p+1} ---")
    for line in text.split("\n"):
        if any(w in line.lower() for w in ["vol", "skew", "smirk", "otm", "atm", "moneyness", "delta", "c_"]):
            print("  ", line)

# 2. Tulchinsky: Chapter 11 (The Triple-Axis Plan) & Chapter 12 (Improving Robustness)
reader_wq = pypdf.PdfReader("docs/research/Tulchinsky_Finding_Alphas_WorldQuant.pdf")
print("\n=== TULCHINSKY CHAPTER 11 & 12 ===")
for p in range(80, 95):
    text = reader_wq.pages[p].extract_text()
    if any(h in text for h in ["Triple-Axis", "Robustness", "Turnover", "Sharpe", "Fitness"]):
        print(f"--- PAGE {p+1} ---")
        lines = [l for l in text.split("\n") if l.strip()]
        print("\n".join("   " + l for l in lines[:15]))
