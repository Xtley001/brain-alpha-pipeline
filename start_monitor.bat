@echo off
title BRAIN Pipeline Monitor
cd /d "C:\Users\pc\Desktop\brain-alpha-pipeline"
"C:\Python314\python.exe" scripts\pipeline_monitor.py --daemon --interval 30 >> "C:\Users\pc\Desktop\brain-alpha-pipeline\logs\pipeline_monitor.log" 2>&1
