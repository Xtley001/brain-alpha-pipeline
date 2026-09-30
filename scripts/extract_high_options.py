import subprocess
import re

def main():
    cmd = ['gh', 'run', 'view', '36635045644', '--log']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')

    pattern = re.compile(r'\[OPTIONS Sim #(\d+)\]\s+([A-Za-z0-9]+)\s+\|\s+Sharpe=([-\d\.]+)\s+\|\s+Fitness=([-\d\.]+)\s+\|\s+TO=([-\d\.]+)%\s+\|\s+Margin=([-\d\.]+)bps\s+\|\s+DD=([-\d\.]+)%\s+\|\s+(.*)')

    high_alphas = []
    for line in proc.stdout:
        m = pattern.search(line)
        if m:
            sim_num, alpha_id, sharpe, fitness, to, margin, dd, arch = m.groups()
            s_val = float(sharpe)
            f_val = float(fitness)
            if s_val >= 1.25 and f_val >= 0.70:
                high_alphas.append({
                    'sim': sim_num,
                    'alpha_id': alpha_id,
                    'sharpe': s_val,
                    'fitness': f_val,
                    'to': float(to),
                    'margin': float(margin),
                    'dd': float(dd),
                    'arch': arch.strip()
                })

    print(f"Total High Alphas Found: {len(high_alphas)}")
    for a in high_alphas:
        print(f"{a['alpha_id']}: Sharpe={a['sharpe']}, Fit={a['fitness']}, TO={a['to']}%, Margin={a['margin']}bps | {a['arch']}")

if __name__ == "__main__":
    main()
