@echo off
rem Detached launcher for the norm-ablation chain (train + targeted study + compare).
cd /d "C:\Users\ompan\OneDrive\Desktop\Lattice QCD Research\dev\InverseRG"
if not exist "out\diffusion_v2\v2_ablate_norm" mkdir "out\diffusion_v2\v2_ablate_norm"
echo ================ ablation launch %date% %time% ================ >> "out\diffusion_v2\v2_ablate_norm\run.log"
".venv\Scripts\python.exe" "diffusion_v2\scripts\run_ablation.py" >> "out\diffusion_v2\v2_ablate_norm\run.log" 2>&1
