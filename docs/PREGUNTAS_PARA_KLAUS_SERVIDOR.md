# Preguntas para Klaus — integrar VLUX Finance OS a nuestro servidor

Responde **solo la configuración y capacidades**, sin proporcionar passwords, cadenas de conexión que incluyan secretos, claves privadas ni tokens.

1. **Sistema operativo** del servidor y arquitectura, recursos disponibles (CPU, RAM y almacenamiento), si es VM o físico.
2. **SQL Server:** versión/edición, nombre de instancia, autenticación (Windows integrada o SQL), ODBC Driver 18 disponible, versión de TLS, si existe una BD DEDICADA para VLUX o si debe crearse. Reporta capacidad, collation y política de respaldos.
3. **Red:** si los clientes acceden por Tailscale, VPN, LAN o Internet; FQDN interno/externo; proxy HTTPS/IIS; certificado vigente; política de firewall. No compartir IP pública si no es necesaria.
4. **Servicio de aplicación:** versión de Python instalada, permisos para servicio Windows/NSSM o Task Scheduler, cuenta de servicio con permisos mínimos, puerto libre para localhost 8765.
5. **Seguridad:** modo de usuarios y grupos, posibilidad de SSO/MFA futuro, registros centralizados, políticas de respaldo y recuperación, acceso remoto y certificados.
6. **Despliegue:** ubicación permitida de archivos de aplicación, proceso de deploy/rollback, quién tiene permisos de administración y copia de seguridad previa.
7. **Compartición:** número de empleados que se conectarán, perfiles (socio, finanzas, consulta) y si necesitan acceso solo por Tailscale o también desde fuera.
8. **Contabilidad:** si hay ERP o sistema de facturas externo del que se quieran importar cobros, gastos e IVA; NO pedir credenciales todavía.

## Resultado que necesito de Klaus

Una ficha breve con: compatibilidad de Python + pyodbc + ODBC 18, instancia/BD de SQL Server, tipo de autenticación, FQDN HTTPS, ruta del servicio, backups, red de acceso y usuarios. Indica lo desconocido explícitamente. **No ejecutar modificaciones ni abrir puertos todavía.**
