import os, sys, requests, dotenv, time
sys.path.insert(0, '.')
dotenv.load_dotenv()
from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient

cfg = OptionsConfig.from_env()
client = BrainClient(cfg.brain_username, cfg.brain_password)
client.authenticate()
s = client._get_session()

sim_url = 'https://api.worldquantbrain.com/simulations/2lDxjaeTJ5aIcshCatmDLCm'
r = s.get(sim_url)
print("Simulation Status Code:", r.status_code)
if r.status_code == 200:
    data = r.json()
    print("Status:", data.get('status'))
    print("IS Metrics:", data.get('is'))
    alpha_id = data.get('alpha')
    print("Alpha ID:", alpha_id)
    if alpha_id:
        chk = s.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}/check")
        if chk.status_code == 200:
            print("Checklist:", chk.json().get('is', {}).get('checks'))
