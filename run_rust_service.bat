@echo off
title RoboBTC DXY Service Runner
echo Checking for Rust / Cargo installation...

where cargo >nul 2>&1
if not %errorLevel% == 0 goto :install_rust

echo [OK] Cargo is installed!
echo Starting the DXY Rust Service...
cd /d "%~dp0\dxy_service"
cargo run --release
goto :eof

:install_rust
echo [ERROR] Rust / Cargo is not in your PATH or is not installed.
echo.
echo To run the service, please install Rust:
echo 1. Download the installer from: https://win.rustup.rs
echo 2. Run the installer and choose default options (Press 1 and Enter).
echo 3. Open a NEW command prompt/PowerShell window and run this script again.
echo.
echo Press any key to open the Rust download page in your browser...
pause >nul
start https://win.rustup.rs
