@echo off
chcp 65001 >nul
rem build_exe.bat  v1.6.0 — сборка solar_calc.exe
rem v1.6.0: шаг «Проверка утечек» (check_leaks.py: токены, пароли) перед сборкой.
rem v1.5.1: нужен Python 3.12+ (было 3.10+).
cd /d "%~dp0"
echo === [1/5] Проверка Python ===
where python >nul 2>nul || (echo Python не найден. Установите Python 3.12+ с python.org & pause & exit /b 1)
python --version
echo === [2/5] Проверка утечек (токены, пароли) ===
python check_leaks.py || (echo Найдены секреты — сборка остановлена & pause & exit /b 1)
echo === [3/5] Установка библиотек ===
python -m pip install --disable-pip-version-check -r requirements.txt || (echo Ошибка установки библиотек & pause & exit /b 1)
echo === [4/5] Сборка PyInstaller ===
python -m PyInstaller --noconfirm --clean solar_calc.spec || (echo Ошибка сборки & pause & exit /b 1)
echo === [5/5] Самопроверка EXE ===
dist\solar_calc.exe --selftest || (echo Самопроверка не прошла & pause & exit /b 1)
echo.
echo Готово: dist\solar_calc.exe
pause
