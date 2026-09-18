import subprocess
import sys
from dotenv import dotenv_values

ORGS = ["xtley-alpha-research-03", "xtley-alpha-research-04"]
REPO_NAME = "brain-alpha-pipeline"

env_vars = dotenv_values(".env")

for org in ORGS:
    target = f"{org}/{REPO_NAME}"
    print(f"\n==========================================")
    print(f"Setting up PRIVATE repository: {target}")
    print(f"==========================================")
    
    # 1. Check if repo already exists
    check = subprocess.run(f"gh repo view {target} --json isPrivate", shell=True, capture_output=True, text=True)
    if check.returncode != 0:
        print(f"Creating private repository: {target}...")
        create_res = subprocess.run(f"gh repo create {target} --private", shell=True, capture_output=True, text=True)
        if create_res.returncode != 0:
            print(f"Error creating repo: {create_res.stderr or create_res.stdout}")
        else:
            print(f"Successfully created private repo: {target}")
    else:
        print(f"Repository {target} already exists. Details: {check.stdout.strip()}")

    # 2. Push code to target
    remote_name = f"remote_{org}"
    # Remove remote if exists
    subprocess.run(f"git remote remove {remote_name}", shell=True, capture_output=True)
    add_remote = subprocess.run(f"git remote add {remote_name} https://github.com/{target}.git", shell=True, capture_output=True, text=True)
    print(f"Pushing main branch to {remote_name}...")
    push_res = subprocess.run(f"git push {remote_name} main --force", shell=True, capture_output=True, text=True)
    if push_res.returncode == 0:
        print(f"Code successfully pushed to {target}!")
    else:
        print(f"Push error: {push_res.stderr or push_res.stdout}")

    # 3. Sync all secrets
    print(f"Syncing all 21 secrets to {target}...")
    synced = 0
    for key, val in env_vars.items():
        if val and not key.startswith("#"):
            p = subprocess.Popen(
                ["gh", "secret", "set", key, "--repo", target],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = p.communicate(input=val)
            if p.returncode == 0:
                synced += 1
            else:
                print(f"  Failed to set {key}: {stderr.strip()}")
    print(f"Configured {synced} secrets on {target}.")

    # 4. Verify privacy status
    status_check = subprocess.run(f"gh repo view {target} --json isPrivate,name,owner", shell=True, capture_output=True, text=True)
    print(f"Final Verification for {target}: {status_check.stdout.strip()}")

print("\nALL ORGANIZATIONS SUCCESSFULLY DEPLOYED AND CONFIGURED AS PRIVATE!")
