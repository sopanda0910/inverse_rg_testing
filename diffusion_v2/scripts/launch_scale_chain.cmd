@echo off
cd /d "C:\Users\ompan\OneDrive\Desktop\Lattice QCD Research\dev\InverseRG"
rem 8 of 12 logical cores: above the campaign's 6-thread thermal-safety point,
rem below the fully-loaded config implicated in the 2026-07-24 bugchecks.
set DIFFUSION_V2_TORCH_THREADS=8
set PYTHONUNBUFFERED=1
echo ================ scale chain launch %date% %time% ================ >> "out\diffusion_v2\ess_chain\scale_chain.log"
".venv\Scripts\python.exe" "diffusion_v2\scripts\run_scale_chain.py" >> "out\diffusion_v2\ess_chain\scale_chain.log" 2>&1
