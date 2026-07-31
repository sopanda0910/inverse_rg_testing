@echo off
rem Detached launcher for the v2 campaign chain. Safe to re-run: every stage
rem resumes from its sentinel / cached outputs.
cd /d "C:\Users\ompan\OneDrive\Desktop\Lattice QCD Research\dev\InverseRG"
if not exist "out\diffusion_v2\v2" mkdir "out\diffusion_v2\v2"
echo ================ campaign launch %date% %time% ================ >> "out\diffusion_v2\v2\run.log"
".venv\Scripts\python.exe" "diffusion_v2\scripts\run_campaign.py" >> "out\diffusion_v2\v2\run.log" 2>&1
