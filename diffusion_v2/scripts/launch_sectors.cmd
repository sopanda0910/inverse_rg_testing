@echo off
cd /d "C:\Users\ompan\OneDrive\Desktop\Lattice QCD Research\dev\InverseRG"
echo ================ sectors launch %date% %time% ================ >> "out\diffusion_v2\v2\sectors.log"
".venv\Scripts\python.exe" "diffusion_v2\scripts\run_sectors.py" >> "out\diffusion_v2\v2\sectors.log" 2>&1
