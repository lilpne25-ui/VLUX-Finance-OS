"""A0 security containment: negative tests on an isolated SQLite in local mode. No real data."""
import json,os,subprocess,sys,tempfile,time,socket,http.client
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
DEMO='DemoVlux2026!'

def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));return s.getsockname()[1]

class Server:
    def __init__(self,mode,dbpath,extra=None):
        self.port=free_port();self.host=f'127.0.0.1:{self.port}'
        env=os.environ.copy();env.update(VLUX_MODE=mode,VLUX_DB='sqlite',VLUX_HOST='127.0.0.1',VLUX_PORT=str(self.port),VLUX_SQLITE_PATH=str(dbpath))
        env.update(extra or {})
        self.proc=subprocess.Popen([sys.executable,str(BASE/'backend/app.py')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                if self.call('GET','/health')[0]==200:return
            except OSError:pass
            time.sleep(.1)
        raise AssertionError('API no inició')
    def call(self,method,path,data=None,cookie='',host=None,origin='same',extra=None):
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=15)
        h={'Host':host or self.host,'X-Requested-With':'VLUX-Desktop'}
        if origin=='same':h['Origin']='http://'+(host or self.host)
        elif origin:h['Origin']=origin
        if cookie:h['Cookie']=cookie
        if extra:h.update(extra)
        body=None
        if data is not None:body=json.dumps(data).encode();h['Content-Type']='application/json'
        c.request(method,path,body=body,headers=h)
        r=c.getresponse();raw=r.read();ctype=r.getheader('Content-Type','')
        payload=json.loads(raw) if 'json' in ctype else raw.decode('utf-8','replace')
        return r.status,payload,r.getheader('Set-Cookie','')
    def stop(self):
        self.proc.terminate();self.proc.wait(timeout=8)

def check(cond,label):
    if not cond:raise AssertionError(label)
    print('PASS',label)

def main():
    with tempfile.TemporaryDirectory(prefix='vlux_a0_') as tmp:
        s=Server('local',Path(tmp)/'a0.sqlite3')
        try:
            # 1. Login page never advertises the public password.
            st,html,_=s.call('GET','/')
            check(st==200 and DEMO not in html and 'vlux.local' not in html,'login sin credenciales demo')
            # 2. Host allowlist (DNS-rebinding protection) on reads and writes.
            check(s.call('GET','/health',host='evil.example:'+str(s.port))[0]==421,'GET con Host ajeno rechazado')
            check(s.call('POST','/api/login',{'email':'ludwing@vlux.local','password':DEMO},host='evil.example:'+str(s.port))[0]==421,'login con Host ajeno rechazado')
            # 3. Origin mandatory and exact on writes.
            check(s.call('POST','/api/login',{'email':'ludwing@vlux.local','password':DEMO},origin='http://evil.example')[0]==403,'Origin ajeno rechazado')
            check(s.call('POST','/api/login',{'email':'ludwing@vlux.local','password':DEMO},origin=None)[0]==403,'POST sin Origin rechazado')
            check(s.call('POST','/api/login',{'email':'ludwing@vlux.local','password':DEMO},extra={'X-Requested-With':''})[0]==403,'POST sin encabezado anti-CSRF rechazado')
            # 4. Public demo password cannot open a session in local mode.
            st,r,cookie=s.call('POST','/api/login',{'email':'ludwing@vlux.local','password':DEMO})
            check(st==403 and r.get('code')=='must_change_password' and not cookie,'contraseña demo no abre sesión en modo local')
            # 5. Replacement rules.
            for bad,label in [('corta1!','contraseña nueva corta rechazada'),(DEMO,'reusar contraseña demo rechazado'),('CAMBIAR_CONTRASENA_UNICA_14_CARACTERES','contraseña de plantilla rechazada')]:
                check(s.call('POST','/api/first-password',{'email':'ludwing@vlux.local','current_password':DEMO,'new_password':bad})[0]==400,label)
            check(s.call('POST','/api/first-password',{'email':'ludwing@vlux.local','current_password':'Incorrecta-123','new_password':'Valida-Nueva-2026'})[0]==403,'cambio inicial con contraseña actual incorrecta rechazado')
            check(s.call('POST','/api/first-password',{'email':'ludwing@vlux.local','current_password':DEMO,'new_password':'Ludwing-Nueva-2026'})[0]==200,'cambio inicial válido aceptado')
            check(s.call('POST','/api/login',{'email':'ludwing@vlux.local','password':DEMO})[0]==403,'contraseña demo ya no funciona')
            st,_,cookie=s.call('POST','/api/login',{'email':'ludwing@vlux.local','password':'Ludwing-Nueva-2026'})
            check(st==200 and 'HttpOnly' in cookie and 'SameSite=Strict' in cookie,'login con contraseña nueva y cookie endurecida')
            L=cookie.split(';')[0]
            check(s.call('POST','/api/change-password',{'current_password':'Ludwing-Nueva-2026','new_password':DEMO},L)[0]==400,'cambio de contraseña a la demo rechazado')
            check(s.call('POST','/api/users',{'name':'Lector','email':'lector@vlux.local','password':DEMO,'role':'consulta'},L)[0]==400,'alta de usuario con contraseña demo rechazada')
            check(s.call('POST','/api/users',{'name':'Socio','email':'socio3@vlux.local','password':'Socio-Tercero-2026','role':'socio'},L)[0]==400,'alta de socio desde la interfaz rechazada')
            # 6. Lockout is per account, not global for the shared proxy IP.
            for _ in range(5):s.call('POST','/api/login',{'email':'nadie@vlux.local','password':'Mala-1234567'})
            check(s.call('POST','/api/first-password',{'email':'rodrigo@vlux.local','current_password':DEMO,'new_password':'Rodrigo-Nueva-2026'})[0]==200,'otro usuario no queda bloqueado por fallos ajenos')
            for _ in range(5):s.call('POST','/api/login',{'email':'rodrigo@vlux.local','password':'Mala-1234567'})
            st,r,_=s.call('POST','/api/login',{'email':'rodrigo@vlux.local','password':'Rodrigo-Nueva-2026'})
            check(st==403 and 'intentos' in r['error'],'cuenta atacada queda bloqueada aun con contraseña correcta')
            check(s.call('POST','/api/login',{'email':'ludwing@vlux.local','password':'Ludwing-Nueva-2026'})[0]==200,'bloqueo no afecta al otro socio')
            # 7. Unauthenticated and read-only access stay closed.
            check(s.call('GET','/api/dashboard')[0]==403,'API sin sesión rechazada')
            check(s.call('POST','/api/first-password',{'email':'consulta@vlux.local','current_password':DEMO,'new_password':'Consulta-Nueva-2026'})[0]==200,'cuenta consulta sustituye contraseña')
            C=s.call('POST','/api/login',{'email':'consulta@vlux.local','password':'Consulta-Nueva-2026'})[2].split(';')[0]
            check(s.call('POST','/api/projects',{'name':'X','client':'Y'},C)[0]==403,'consulta no puede escribir')
            check(s.call('PUT','/api/settings',{'reserve_target_cents':0},C)[0]==403,'consulta no cambia parámetros')
            check(s.call('POST','/api/collab/people',{'name':'X','specialty':'Y'},C)[0]==403,'consulta no crea colaboradores')
        finally:
            s.stop()
        # 8. Demo mode (fictitious data only) keeps the public password usable.
        d=Server('demo',Path(tmp)/'demo.sqlite3')
        try:
            check(d.call('POST','/api/login',{'email':'ludwing@vlux.local','password':DEMO})[0]==200,'modo demo conserva acceso de prueba')
        finally:
            d.stop()
        # 9. Proxy header ignored unless explicitly trusted.
        p=Server('local',Path(tmp)/'proxy.sqlite3')
        try:
            for i in range(25):p.call('POST','/api/login',{'email':f'x{i}@vlux.local','password':'Mala-1234567'},extra={'X-Forwarded-For':f'10.0.0.{i}'})
            st,r,_=p.call('POST','/api/login',{'email':'otro@vlux.local','password':'Mala-1234567'})
            check(st==403 and 'intentos' in r['error'],'X-Forwarded-For falsificado no evade límite por IP')
        finally:
            p.stop()
    print('PASS: A0 contención de seguridad')

if __name__=='__main__':main()
