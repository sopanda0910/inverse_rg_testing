@echo off
cd /d "C:\Users\ompan\OneDrive\Desktop\Lattice QCD Research\dev\InverseRG"
echo ================ followup launch %date% %time% ================ >> "out\diffusion_v2\v2\followup.log"
".venv\Scripts\python.exe" "diffusion_v2\scripts\run_followup.py" >> "out\diffusion_v2\v2\followup.log" 2>&1
