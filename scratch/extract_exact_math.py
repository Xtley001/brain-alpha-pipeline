import pypdf
import re

def extract_section(pdf_path, search_terms, max_pages=5):
    reader = pypdf.PdfReader(pdf_path)
    extracted = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ''
        for term in search_terms:
            if re.search(r'\b' + re.escape(term) + r'\b', text, re.IGNORECASE):
                extracted.append((i+1, term, text))
                break
        if len(extracted) >= max_pages:
            break
    return extracted

# 1. Xing Zhang Zhao: Smirk definition
print("=== XING ZHANG ZHAO SMIRK FORMULATION ===")
res = extract_section("docs/research/Xing_Zhang_Zhao_Volatility_Smirk.pdf", ["VOLOTMP", "VOLATMC", "SKEW", "measure the steepness"], max_pages=3)
for page_num, term, text in res:
    print(f"--- Page {page_num} (Term: {term}) ---")
    for line in text.split('\n'):
        if any(w in line.lower() for w in ['vol', 'skew', 'smirk', 'otm', 'atm', 'equation', '=']):
            print("  ", line[:120])

# 2. Bali Hovakimian: Volatility Spreads
print("\n=== BALI HOVAKIMIAN VOLATILITY SPREADS ===")
res = extract_section("docs/research/Bali_Hovakimian_Volatility_Spreads.pdf", ["VS_C", "VS_P", "RVol", "IVol", "spread"], max_pages=3)
for page_num, term, text in res:
    print(f"--- Page {page_num} (Term: {term}) ---")
    for line in text.split('\n'):
        if any(w in line.lower() for w in ['spread', 'vol', 'call', 'put', 'realized', 'implied', '=']):
            print("  ", line[:120])

# 3. Pan Poteshman: Option Volume / PCR
print("\n=== PAN POTESHMAN OPTION VOLUME / PCR ===")
res = extract_section("docs/research/Pan_Poteshman_Option_Volume.pdf", ["put-call", "O/S", "buyer-initiated", "volume ratio"], max_pages=3)
for page_num, term, text in res:
    print(f"--- Page {page_num} (Term: {term}) ---")
    for line in text.split('\n'):
        if any(w in line.lower() for w in ['volume', 'put', 'call', 'ratio', 'trade', 'open', '=']):
            print("  ", line[:120])
