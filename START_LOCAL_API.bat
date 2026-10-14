@echo off
setlocal EnableExtensions DisableDelayedExpansion
title VLUX Finance OS - API local
pushd "%~dp0"
if errorlevel 1 goto PATH_ERROR
set "VLUX_MODE=local"
set "VLUX_DB=sqlite"
set "VLUX_HOST=127.0.0.1"
set "VLUX_PORT=8765"
set "VLUX_OPEN_BROWSER=0"
if not defined LOCALAPPDATA set "LOCALAPPDATA=%USERPROFILE%\AppData\Local"
set "VLUX_SQLITE_PATH=%LOCALAPPDATA%\VLUX\FinanceOS\vlux_clean.sqlite3"
echo URL: http://127.0.0.1:8765
where python >nul 2>nul
if not errorlevel 1 (
  python -c "import sys;sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
  if not errorlevel 1 goto RUN_PYTHON
)
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys;sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
  if not errorlevel 1 goto RUN_PY
)
echo [ERROR] Python 3.11+ no encontrado.
goto ERROR_EXIT
:RUN_PYTHON
python "backend\app.py"
set "CODE=%ERRORLEVEL%"
goto DONE
:RUN_PY
py -3 "backend\app.py"
set "CODE=%ERRORLEVEL%"
goto DONE
:PATH_ERROR
echo [ERROR] No se pudo acceder a la carpeta compartida.
:ERROR_EXIT
set "CODE=1"
:DONE
if not "%CODE%"=="0" pause
popd
exit /b %CODE%
