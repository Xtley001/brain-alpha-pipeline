import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient

cfg = OptionsConfig.from_env()

async def check():
    client = BrainClient(cfg.brain_username, cfg.brain_password)
    client.authenticate()
    session = client._get_session()
    # Check alpha mLmkaxd6 details
    resp = session.get('https://api.worldquantbrain.com/alphas/mLmkaxd6')
    print('Alpha mLmkaxd6 HTTP status:', resp.status_code)
    data = resp.json()
    print('Status field:', data.get('status'))
    print('Stage field:', data.get('stage'))
    print('Type field:', data.get('type'))
    print('Name:', data.get('name'))
    print('Date created:', data.get('dateCreated'))
    print('Date submitted:', data.get('dateSubmitted'))
    
    # Check user submissions via API
    sub_resp = session.get('https://api.worldquantbrain.com/users/self/alphas?status=SUBMITTED&limit=10')
    if sub_resp.status_code == 200:
        results = sub_resp.json().get('results', [])
        print(f"\nUser SUBMITTED alphas count returned: {len(results)}")
        for a in results:
            print(f" - {a.get('id')} | {a.get('name')} | Status: {a.get('status')} | Date: {a.get('dateSubmitted')}")

    # Also check /users/self/alphas without status filter
    all_resp = await client.session.get('https://api.worldquantbrain.com/users/self/alphas?limit=10')
    if all_resp.status_code == 200:
        results = all_resp.json().get('results', [])
        print(f"\nMost recent 10 alphas owned by user:")
        for a in results:
            print(f" - {a.get('id')} | {a.get('name')} | Status: {a.get('status')} | DateSubmitted: {a.get('dateSubmitted')}")

asyncio.run(check())
