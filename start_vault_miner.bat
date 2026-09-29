@echo off
title BRAIN Vault Miner (Options)
cd /d "C:\Users\pc\Desktop\brain-alpha-pipeline"
"C:\Python314\python.exe" scripts\autonomous_24h_vault_miner.py >> "C:\Users\pc\Desktop\brain-alpha-pipeline\logs\autonomous_vault_miner.log" 2>&1
