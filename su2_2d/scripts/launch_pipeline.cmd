@echo off
rem First SU(2) pipeline run: smoke -> data -> train -> lift (~35 min).
rem Validated thermal-safety recipe: EcoQoS as-is, no priority games,
rem 8 threads, never parallel worker processes.
cd /d "C:\Users\ompan\OneDrive\Desktop\Lattice QCD Research\dev\InverseRG"
set SU2_2D_TORCH_THREADS=8
set PYTHONUNBUFFERED=1
if not exist "out\su2_2d" mkdir "out\su2_2d"
echo ================ su2 pipeline launch %date% %time% ================ >> "out\su2_2d\pipeline.log"
".venv\Scripts\python.exe" "su2_2d\scripts\run_pipeline.py" >> "out\su2_2d\pipeline.log" 2>&1
