"""
Automated Secret Sync and Repo Setup Utility for GitHub Organizations.
Uses gh CLI and local .env to fork repo and copy all 21 secrets to a new organization.
"""
import subprocess
import sys
from dotenv import dotenv_values


def setup_org_repo(org_name: str, repo_name: str = "brain-alpha-pipeline"):
    print(f"=== Setting up {org_name}/{repo_name} ===")
    
    # 1. Check if repo exists in org, if not fork or push
    check = subprocess.run(f"gh repo view {org_name}/{repo_name}", shell=True, capture_output=True, text=True)
    if check.returncode != 0:
        print(f"Creating / forking {repo_name} into organization {org_name}...")
        fork_cmd = f"gh repo fork Xtley001/{repo_name} --org {org_name} --clone=false"
        res = subprocess.run(fork_cmd, shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"Fork output: {res.stderr or res.stdout}")
        else:
            print(f"Successfully forked to {org_name}/{repo_name}")
    else:
        print(f"Repository {org_name}/{repo_name} already exists.")

    # 2. Sync secrets from local .env
    env_vars = dotenv_values(".env")
    target_repo = f"{org_name}/{repo_name}"
    
    print(f"Syncing secrets to {target_repo}...")
    success_count = 0
    for key, val in env_vars.items():
        if val and not key.startswith("#"):
            # Set secret via gh secret set
            p = subprocess.Popen(
                ["gh", "secret", "set", key, "--repo", target_repo],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = p.communicate(input=val)
            if p.returncode == 0:
                print(f" - [OK] Secret: {key}")
                success_count += 1
            else:
                print(f" - [FAIL] Secret {key}: {stderr.strip()}")

    print(f"\nCompleted! {success_count} secrets successfully configured on {target_repo}.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scratch/sync_secrets_to_org.py <ORG_NAME>")
        sys.exit(1)
    setup_org_repo(sys.argv[1])
