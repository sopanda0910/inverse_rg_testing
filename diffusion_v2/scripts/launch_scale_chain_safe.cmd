@echo off
rem Safe-mode relaunch: the campaign's validated 6-thread thermal-safety point.
rem Used by the watcher after any critical system event.
cd /d "C:\Users\ompan\OneDrive\Desktop\Lattice QCD Research\dev\InverseRG"
set DIFFUSION_V2_TORCH_THREADS=6
set PYTHONUNBUFFERED=1
echo ================ scale chain SAFE relaunch %date% %time% ================ >> "out\diffusion_v2\ess_chain\scale_chain.log"
".venv\Scripts\python.exe" "diffusion_v2\scripts\run_scale_chain.py" >> "out\diffusion_v2\ess_chain\scale_chain.log" 2>&1
