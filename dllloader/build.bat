@echo off
pyinstaller --onefile --name dllloader --console dllloader.py
echo.
echo Build complete. Output: dist\dllloader.exe
