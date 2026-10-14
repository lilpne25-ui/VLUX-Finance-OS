@echo off
setlocal EnableExtensions DisableDelayedExpansion
title VLUX Finance OS - Pruebas
pushd "%~dp0"
if errorlevel 1 goto PATH_ERROR
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
python "tests\smoke_test.py" && python "tests\clean_mode_test.py" && python "tests\collab_public_test.py"
set "CODE=%ERRORLEVEL%"
goto DONE
:RUN_PY
py -3 "tests\smoke_test.py" && py -3 "tests\clean_mode_test.py" && py -3 "tests\collab_public_test.py"
set "CODE=%ERRORLEVEL%"
goto DONE
:PATH_ERROR
echo [ERROR] No se pudo acceder a esta carpeta.
:ERROR_EXIT
set "CODE=1"
:DONE
if "%CODE%"=="0" (echo [OK] Pruebas completadas.) else (echo [ERROR] Las pruebas fallaron con codigo %CODE%.)
popd
pause
exit /b %CODE%
