import subprocess
from dotenv import dotenv_values

TARGET = "xtley-alpha-research-04/brain-alpha-pipeline"
env_vars = dotenv_values(".env")

print(f"Setting secrets on {TARGET}...")
count = 0
for k, v in env_vars.items():
    if v and not k.startswith("#"):
        cmd = ["gh", "secret", "set", k, "-b", v, "--repo", TARGET]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            count += 1
            print(f" - [OK] {k}")
        else:
            print(f" - [FAIL] {k}: {res.stderr.strip()}")

print(f"\nDone! Configured {count} secrets on {TARGET}.")
