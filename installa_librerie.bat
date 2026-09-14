@echo off
title Installatore Librerie - Suite Multimediale di Daniele Barile
echo ======================================================
echo Installazione delle dipendenze per la Suite Multimediale di Daniele Barile...
echo ======================================================

:: Rilevamento ambiente virtuale (per installare nel posto corretto)
set PY="python"
if exist .venv\Scripts\python.exe (
    set PY=".venv\Scripts\python.exe"
) else if exist venv\Scripts\python.exe (
    set PY="venv\Scripts\python.exe"
)

echo Utilizzo interprete: %PY%
%PY% -m pip install --upgrade pip setuptools wheel
%PY% -m pip install Pillow moviepy PyQt6 PyQt6-WebEngine python-docx odfpy pymupdf fpdf2 matplotlib opencv-python pyautogui numpy sounddevice imageio-ffmpeg soundfile
echo.
echo Operazione completata. Tutte le librerie sono state installate.
pause