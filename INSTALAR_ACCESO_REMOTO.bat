@echo off
setlocal
set /p "VLUX_URL=URL HTTPS del servidor de VLUX (ej. https://finanzas.vlux.com.mx): "
if "%VLUX_URL:~0,8%" NEQ "https://" (
 echo [ERROR] Por seguridad se exige HTTPS.
 pause
 exit /b 1
)
set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" set "EDGE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" (echo [ERROR] Microsoft Edge no disponible.&pause&exit /b 1)
start "" "%EDGE%" --app="%VLUX_URL%" --window-size=1440,900
