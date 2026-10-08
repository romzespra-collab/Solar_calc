@echo off
chcp 65001 >nul
rem build_exe.bat  v1.2.0 — сборка solar_calc.exe
cd /d "%~dp0"
echo === [1/4] Проверка Python ===
where python >nul 2>nul || (echo Python не найден. Установите Python 3.10+ с python.org & pause & exit /b 1)
python --version
echo === [2/4] Установка библиотек ===
python -m pip install --disable-pip-version-check -r requirements.txt || (echo Ошибка установки библиотек & pause & exit /b 1)
echo === [3/4] Сборка PyInstaller ===
python -m PyInstaller --noconfirm --clean solar_calc.spec || (echo Ошибка сборки & pause & exit /b 1)
echo === [4/4] Самопроверка EXE ===
dist\solar_calc.exe --selftest || (echo Самопроверка не прошла & pause & exit /b 1)
echo.
echo Готово: dist\solar_calc.exe
pause
