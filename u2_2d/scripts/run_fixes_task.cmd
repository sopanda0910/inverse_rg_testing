@echo off
REM Launcher for the unattended U(2) fix queue, used by the scheduled task.
REM
REM Its only job is to set the working directory and hand off to the PowerShell
REM queue. schtasks /TR has no working-directory option and quoting a full
REM PowerShell command line through it is a reliable source of silent breakage,
REM so the indirection is deliberate.
REM
REM   schtasks /Create /TN U2FixQueue /TR "<this file>" /SC ONCE /ST 23:59 /F
REM   schtasks /Run    /TN U2FixQueue
REM   schtasks /End    /TN U2FixQueue     (stop it)
REM
REM Running it detached from the editor is the point: CLAUDE.md records that
REM long runs launched from an editor-attached shell die with the editor.

cd /d "%~dp0..\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "u2_2d\scripts\run_fixes.ps1" > "out\u2_2d\logs\run_fixes.log" 2>&1
