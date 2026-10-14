@echo off
setlocal EnableExtensions DisableDelayedExpansion
title VLUX Finance OS - Demo local
REM V0.1.1: PUSHD convierte rutas UNC (\\servidor\carpeta) en unidad temporal.
REM No usar cd /d %%~dp0: CMD no admite UNC como directorio activo.
pushd "%~dp0"
if errorlevel 1 goto PATH_ERROR
set "VLUX_MODE=demo"
set "VLUX_DB=sqlite"
set "VLUX_HOST=127.0.0.1"
set "VLUX_PORT=8765"
set "VLUX_OPEN_BROWSER=1"
REM Cada usuario tiene su base en su propio perfil Windows, NUNCA en SMB.
if not defined LOCALAPPDATA set "LOCALAPPDATA=%USERPROFILE%\AppData\Local"
set "VLUX_SQLITE_PATH=%LOCALAPPDATA%\VLUX\FinanceOS\vlux_local.sqlite3"
echo.
echo VLUX Finance OS v0.3 - Demo con cifras ficticias
echo Carpeta de programa: %CD%
echo Base de datos privada local: %VLUX_SQLITE_PATH%
echo Direccion local: http://127.0.0.1:8765
echo.
echo Esta ventana mantiene el servidor encendido. Para cerrar presiona CTRL+C.
echo Si el puerto 8765 ya esta ocupado, cierra el otro servidor VLUX.
echo.
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
echo [ERROR] Instala Python 3.11 o superior. Tu Python 3.14 es compatible.
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
echo [ERROR] No pude acceder a esta carpeta compartida. Verifica permisos y conexion de red.
goto ERROR_EXIT
:ERROR_EXIT
set "CODE=1"
:DONE
if not "%CODE%"=="0" (
 echo.
 echo [ERROR] VLUX Finance OS termino con codigo %CODE%.
 echo Revisa el mensaje de error arriba.
 pause
)
popd
exit /b %CODE%
