@echo off
rem Post-audit chain: repairs + matching-residual decomposition + AIS transport
rem + validation rerun + fresh-seed reruns + L=64 head-to-head.
rem Validated thermal-safety recipe: EcoQoS as-is, no priority games, 8 threads
rem (the scale chain's field-validated single-process ceiling; do NOT add
rem parallel worker processes -- that is what crashed the machine 2026-07-24).
cd /d "C:\Users\ompan\OneDrive\Desktop\Lattice QCD Research\dev\InverseRG"
set DIFFUSION_V2_TORCH_THREADS=8
set PYTHONUNBUFFERED=1
if not exist "out\diffusion_v2\audit_chain" mkdir "out\diffusion_v2\audit_chain"
echo ================ audit chain launch %date% %time% ================ >> "out\diffusion_v2\audit_chain\chain.log"
".venv\Scripts\python.exe" "diffusion_v2\scripts\run_audit_chain.py" >> "out\diffusion_v2\audit_chain\chain.log" 2>&1
