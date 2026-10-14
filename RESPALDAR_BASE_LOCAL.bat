@echo off
setlocal EnableExtensions DisableDelayedExpansion
title VLUX Finance OS - Respaldo local
pushd "%~dp0"
if errorlevel 1 (echo No puedo acceder a la carpeta. & pause & exit /b 1)
if not defined LOCALAPPDATA set "LOCALAPPDATA=%USERPROFILE%\AppData\Local"
set "ROOTDB=%LOCALAPPDATA%\VLUX\FinanceOS"
echo Antes de respaldar cierra otras sesiones de VLUX Finance OS.
if not exist "%ROOTDB%" (echo No hay bases locales que respaldar. & goto DONE)
where py >nul 2>nul
if not errorlevel 1 goto USE_PY
where python >nul 2>nul
if not errorlevel 1 goto USE_PYTHON
echo Python 3.11+ no encontrado.
goto ERROR
:USE_PY
set "RUNPY=py -3"
goto RUN
:USE_PYTHON
set "RUNPY=python"
:RUN
if exist "%ROOTDB%\vlux_clean.sqlite3" (
 set "VLUX_SQLITE_PATH=%ROOTDB%\vlux_clean.sqlite3"
 %RUNPY% "backend\backup_sqlite.py"
 if errorlevel 1 goto ERROR
)
if exist "%ROOTDB%\vlux_local.sqlite3" (
 set "VLUX_SQLITE_PATH=%ROOTDB%\vlux_local.sqlite3"
 %RUNPY% "backend\backup_sqlite.py"
 if errorlevel 1 goto ERROR
)
echo Respaldos dentro de %ROOTDB%\backups
goto DONE
:ERROR
echo [ERROR] Revisa que tu base no este abierta.
pause
popd
exit /b 1
:DONE
echo [OK] Proceso terminado.
pause
popd
exit /b 0
