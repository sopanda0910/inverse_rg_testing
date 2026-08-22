$py = ".venv\Scripts\python.exe"
& $py -u u2_2d/scripts/36_transport_check.py --device cuda --coarse-size 16 `
    --coarse-betas "8.0115,23.6203,45.4637,105.244,199.229,328.665" `
    --n-configs 64 --out-dir out/u2_2d/transport_check/L16
& $py -u u2_2d/scripts/36_transport_check.py --device cuda --coarse-size 32 `
    --coarse-betas "8.3757,23.3695,46.4473,105.423" `
    --n-configs 64 --out-dir out/u2_2d/transport_check/L32
