@echo off
rem Detached launcher for the overnight follow-up chain (head-to-head highstats,
rem burn-in scan, ESS guidance attribution). Safe to re-run: stages resume.
cd /d "C:\Users\ompan\OneDrive\Desktop\Lattice QCD Research\dev\InverseRG"
echo ================ overnight launch %date% %time% ================ >> "out\diffusion_v2\overnight.log"
".venv\Scripts\python.exe" "diffusion_v2\scripts\run_overnight.py" >> "out\diffusion_v2\overnight.log" 2>&1
