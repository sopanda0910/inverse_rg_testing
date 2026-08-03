@echo off
rem Exactness follow-up: certificate closure check + rich-basis sector-resolved
rem AIS + L=64 instanton burn-in scan. WAITS for the audit chain's CHAIN_DONE
rem before doing any heavy work, so launching early is safe.
rem Validated thermal-safety recipe: EcoQoS as-is, no priority games, 8 threads
rem (field-validated single-process ceiling; never add parallel workers).
cd /d "C:\Users\ompan\OneDrive\Desktop\Lattice QCD Research\dev\InverseRG"
set DIFFUSION_V2_TORCH_THREADS=8
set PYTHONUNBUFFERED=1
if not exist "out\diffusion_v2\exactness2" mkdir "out\diffusion_v2\exactness2"
echo ================ exactness2 launch %date% %time% ================ >> "out\diffusion_v2\exactness2\chain.log"
".venv\Scripts\python.exe" "diffusion_v2\scripts\run_exactness2.py" >> "out\diffusion_v2\exactness2\chain.log" 2>&1
