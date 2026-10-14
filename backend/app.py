"""VLUX Finanzas | zero-dependency web service for desktop Edge application.
Production: run behind HTTPS reverse proxy with SQL Server; never expose this
Python HTTP server directly to the Internet or LAN without TLS/auth controls.
"""
import base64, csv, hashlib, hmac, io, json, os, re, secrets, sys, threading, time, subprocess
from datetime import datetime, timezone, timedelta, date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from db import DB, initialize, MODE, DEFAULT_SETTINGS, DB_PATH
import collab
ROOT = Path(__file__).resolve().parent.parent
FRONT = ROOT / 'frontend'
MODE_APP = os.getenv('VLUX_MODE','demo').lower()
HOST = os.getenv('VLUX_HOST','127.0.0.1')
PORT = int(os.getenv('VLUX_PORT','8765'))
MAX_BODY = 150_000
LOGIN_FAILS={}
FAIL_LOCK=threading.Lock()

def now():return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def iso_today():return date.today().isoformat()
def sha(s):return hashlib.sha256(s.encode('utf-8')).hexdigest()
def encode_pwd(password):
    salt=secrets.token_bytes(20)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,310000)
    return 'pbkdf2_sha256$310000$'+base64.b64encode(salt).decode()+'$'+base64.b64encode(digest).decode()
def verify_pwd(password,encoded):
    try:
        algo,iter_,salt_b64,hash_b64=encoded.split('$')
        if algo!='pbkdf2_sha256':return False
        expected=base64.b64decode(hash_b64)
        actual=hashlib.pbkdf2_hmac('sha256',password.encode(),base64.b64decode(salt_b64),int(iter_))
        return hmac.compare_digest(actual,expected)
    except Exception:return False

def check_str(x,field,maxlen=300,optional=False):
    if not isinstance(x,str) or (not optional and not x.strip()) or len(x)>maxlen:raise UserError(f'Campo {field} inválido')
    return x.strip()
def cents(x):
    if isinstance(x,bool) or not isinstance(x,int) or x<=0 or x>2_000_000_000_00:raise UserError('El monto debe ser positivo y expresado en centavos enteros')
    return x
def valid_date(s):
    check_str(s,'fecha',10)
    try:date.fromisoformat(s)
    except Exception:raise UserError('Fecha inválida: AAAA-MM-DD')
    return s
def valid_period(s):
    if not isinstance(s,str) or not re.fullmatch(r'20\d\d-(0[1-9]|1[0-2])',s):raise UserError('Periodo inválido: AAAA-MM')
    return s
class UserError(Exception):pass
class Forbidden(Exception):pass

def audit(db,uid,action,entity,eid,detail=''):
    db.insert('audit',['created_at','actor_id','action','entity','entity_id','detail'],[now(),uid,action,entity,eid,str(detail)[:1100]])

def get_settings(db):
    out=dict(DEFAULT_SETTINGS)
    for r in db.rows('SELECT {key} AS k, {value} AS v FROM {settings}'):
        k,v=r['k'],r['v']
        if k in DEFAULT_SETTINGS and isinstance(DEFAULT_SETTINGS[k],int):
            try:out[k]=int(v)
            except Exception:pass
        else:out[k]=v
    return out

def get_users(db):
    return db.rows('SELECT id,name,email,role,active,created_at FROM {users} ORDER BY id')

def get_projects(db):
    return db.rows('SELECT * FROM {projects} ORDER BY id DESC')

def get_transactions(db):
    return db.rows('SELECT t.*,p.name AS project_name,u.name AS created_by_name,recipient.name AS recipient_name FROM {transactions} t LEFT JOIN {projects} p ON p.id=t.project_id LEFT JOIN {users} u ON u.id=t.created_by LEFT JOIN {users} recipient ON recipient.id=t.recipient_user_id ORDER BY t.txn_date DESC,t.id DESC')

def compute_stats(db):
    ts=get_transactions(db)
    totals={'income_cents':0,'expense_cents':0,'capital_cents':0,'distribution_cents':0}
    monthly={}
    by_project={}
    for t in ts:
        if t['status']!='vigente':continue
        kind=t['kind']; val=int(t['amount_cents'])
        if kind in ('income','expense','capital','distribution'):
            totals[kind+'_cents']+=val
        ym=t['txn_date'][:7]
        if ym not in monthly:monthly[ym]={'month':ym,'income_cents':0,'expense_cents':0}
        if kind in ('income','expense'):monthly[ym][kind+'_cents']+=val
        if t['project_id'] and kind in ('income','expense'):
            p=by_project.setdefault(str(t['project_id']),{'income_cents':0,'expense_cents':0})
            p[kind+'_cents']+=val
    income=totals['income_cents'];expenses=totals['expense_cents'];capital=totals['capital_cents'];div=totals['distribution_cents']
    s=get_settings(db)
    return {
        **totals,'balance_cents':income+capital-expenses-div,
        'operating_profit_cents':income-expenses,
        'free_cash_cents':max(0,income+capital-expenses-div-int(s['reserve_target_cents'])),
        'candidate_dividend_capacity_cents':max(0,int(max(0,income-expenses)*(100-int(s['planning_tax_pct']))/100*0.30)-div),
        'reserve_target_cents':int(s['reserve_target_cents']),
        'monthly':sorted(monthly.values(),key=lambda a:a['month'])[-12:],
        'by_project':by_project,
        'break_even_no_salary_cents':int(int(s['monthly_fixed_cents'])/(1-int(s['variable_cost_pct'])/100)) if s['variable_cost_pct']<100 else None,
        'total_transactions':len(ts),
        'pending_expenses_cents':sum(int(t['amount_cents']) for t in ts if t['status']=='pendiente' and t['kind']=='expense'),
        'pending_approvals':sum(1 for t in ts if t['status']=='pendiente'),
        'disclaimer':'Cifras operativas preliminares; no sustituyen contabilidad, conciliación bancaria ni declaración de impuestos.'
    }

def local_clean_seed(db):
    """Isolated local test accounts; no example clients, movements or forecasts.

    Intended for UI validation only. Never expose local credentials on a network.
    """
    if db.one('SELECT COUNT(*) AS n FROM {users}')['n']:
        return
    pw=encode_pwd('DemoVlux2026!')
    for name,email,role in [
        ('Ludwing Valdés','ludwing@vlux.local','socio'),
        ('Rodrigo Lira','rodrigo@vlux.local','socio'),
        ('Cuenta de consulta','consulta@vlux.local','consulta')]:
        db.insert('users',['name','email','password_hash','role','active','created_at'],
                  [name,email,pw,role,1,now()])
    audit(db,None,'INITIALIZED_CLEAN','system',None,
          'Usuarios temporales; cero movimientos, cero proyectos, cero pronósticos.')
    db.commit()

def demo_seed(db):
    users=db.one('SELECT COUNT(*) AS n FROM {users}')['n']
    if users:return
    pw=encode_pwd('DemoVlux2026!')
    for name,email in [('Ludwing Valdés','ludwing@vlux.local'),('Rodrigo Lira','rodrigo@vlux.local')]:
        db.insert('users',['name','email','password_hash','role','active','created_at'],[name,email,pw,'socio',1,now()])
    db.insert('users',['name','email','password_hash','role','active','created_at'],['Invitado de consulta','consulta@vlux.local',pw,'consulta',1,now()])
    pid=[]
    for name,client,budget,status in [('VLUX POS','Producto VLUX',1200000,'activo'),('Braille CRM','Cliente demostración',16000000,'activo'),('SGC ISO 9001','Prospecto demostración',35000000,'cotizado')]:
        pid.append(db.insert('projects',['name','client','budget_cents','status','created_at'],[name,client,budget,status,now()]))
    today=date.today();months=[]
    for offset in range(5,-1,-1):
        yy=today.year;mm=today.month-offset
        while mm<=0:yy-=1;mm+=12
        months.append(f'{yy:04d}-{mm:02d}-12')
    for ix,d in enumerate(months):
        inc=[12000,28000,41000,62000,78000,92000][ix]*100
        exp=[4000,11000,15000,26000,32000,35000][ix]*100
        for kind,amount,cat,desc,proj in [('income',inc,'Servicios de software','Cobro de proyecto (DEMO)',pid[ix%2]),('expense',exp,'Proveedores y operación','Gasto registrado (DEMO)',pid[ix%2])]:
            db.insert('transactions',['txn_date','kind','amount_cents','category','description','project_id','recipient_user_id','reference','status','created_by','created_at'],[d,kind,amount,cat,desc,proj,None,'DEMO-'+str(ix+1),'vigente',1,now()])
    # Revenue plan 12 months for demo; all figures fictitious.
    yy=today.year; mm=today.month
    for index in range(12):
        y=yy+(mm-1+index)//12; m=(mm-1+index)%12+1
        db.insert('forecasts',['period','revenue_cents','notes','updated_by','updated_at'],[f'{y:04d}-{m:02d}',[15000,25000,35000,40000,50000,60000,70000,80000,85000,90000,100000,115000][index]*100,'Plan hipotético DEMO',1,now()])
    audit(db,1,'SEED_DEMO','system',None,'Datos ficticios; no son cifras reales de VLUX')
    db.commit()

def bootstrap():
    if MODE_APP not in ('demo','local','production'):raise RuntimeError('VLUX_MODE debe ser demo, local o production')
    if MODE_APP in ('local','demo') and (HOST not in ('127.0.0.1','localhost','::1') or MODE!='sqlite'):
        raise RuntimeError('La prueba local o demo exige SQLite y escucha sólo en localhost')
    if MODE_APP=='production':
        if MODE!='sqlserver':raise RuntimeError('PRODUCTION requiere VLUX_DB=sqlserver para evitar bases locales compartidas')
        if HOST not in ('127.0.0.1','localhost','::1'):raise RuntimeError('Backend productivo sólo debe escuchar en loopback tras un proxy HTTPS')
        if not os.environ.get('VLUX_PUBLIC_ORIGIN','').startswith('https://'):raise RuntimeError('VLUX_PUBLIC_ORIGIN debe iniciar con https://')
    initialize();db=DB()
    collab.seed(db)
    try:
        if MODE_APP=='demo' and MODE=='sqlite':demo_seed(db)
        if MODE_APP=='local' and MODE=='sqlite':local_clean_seed(db)
        if MODE_APP=='production' and not db.one('SELECT id FROM {users}'):
            email=os.getenv('VLUX_BOOTSTRAP_ADMIN_EMAIL','').strip().lower();pw=os.getenv('VLUX_BOOTSTRAP_ADMIN_PASSWORD','')
            if not email or len(pw)<14:raise RuntimeError('Primer arranque: configure VLUX_BOOTSTRAP_ADMIN_EMAIL y contraseña de mínimo 14 caracteres')
            db.insert('users',['name','email','password_hash','role','active','created_at'],[os.getenv('VLUX_BOOTSTRAP_ADMIN_NAME','Ludwing Valdés'),email,encode_pwd(pw),'socio',1,now()])
            audit(db,None,'BOOTSTRAP','users',1,'Administrador inicial creado')
            db.commit()
    finally:db.close()

class Handler(BaseHTTPRequestHandler):
    server_version='VLUXFinanzas/0.3'
    def log_message(self, fmt, *args):
        # Avoid logging credentials, body, session cookies or query tokens.
        print(f'[{now()}] {self.client_address[0]} {fmt%args}',flush=True)
    def send(self,code,payload=None,ctype='application/json',headers=None):
        raw=(json.dumps(payload,ensure_ascii=False,default=str).encode('utf8') if ctype=='application/json' else payload)
        self.send_response(code)
        self.send_header('Content-Type',ctype+'; charset=utf-8' if ctype.startswith(('application/json','text/')) else ctype)
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store' if ctype=='application/json' else 'no-cache')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        if headers:
            for k,v in headers:self.send_header(k,v)
        self.end_headers();self.wfile.write(raw)
    def body(self):
        length=int(self.headers.get('Content-Length','0'))
        if length<=0 or length>MAX_BODY:raise UserError('JSON requerido o tamaño excedido')
        if self.headers.get('Content-Type','').split(';')[0].strip()!='application/json':raise UserError('Content-Type debe ser application/json')
        if self.headers.get('X-Requested-With','')!='VLUX-Desktop':raise Forbidden('Solicitud sin encabezado de protección')
        origin=self.headers.get('Origin','')
        expected=os.environ.get('VLUX_PUBLIC_ORIGIN','') if MODE_APP=='production' else f'http://{self.headers.get("Host", "")}'
        if origin and origin.rstrip('/')!=expected.rstrip('/'):
            raise Forbidden('Origen no autorizado')
        try:obj=json.loads(self.rfile.read(length))
        except Exception:raise UserError('JSON inválido')
        if not isinstance(obj,dict):raise UserError('Se requiere un objeto JSON')
        return obj
    def user(self,db):
        cookie=self.headers.get('Cookie','');token=''
        for part in cookie.split(';'):
            if part.strip().startswith('vlux_session='):
                token=part.strip().split('=',1)[1];break
        if not token:return None
        sess=db.one('SELECT s.user_id,s.expires_at,u.id,u.name,u.email,u.role,u.active FROM {sessions} s JOIN {users} u ON u.id=s.user_id WHERE s.token_hash=?',(sha(token),))
        if not sess or not sess['active'] or sess['expires_at']<now():return None
        return {'id':sess['id'],'name':sess['name'],'email':sess['email'],'role':sess['role']}
    def require(self,db,write=False):
        u=self.user(db)
        if not u:raise Forbidden('Sesión caducada o no iniciada')
        if write and u['role']!='socio':raise Forbidden('Cuenta de solo consulta')
        return u
    def cookie(self,token='',maxage=0):
        return ('Set-Cookie','vlux_session='+token+'; Path=/; HttpOnly; SameSite=Strict; Max-Age='+str(maxage)+('; Secure' if MODE_APP=='production' else ''))
    def do_GET(self):
        path=urlparse(self.path).path
        if not path.startswith('/api/') and path!='/health':
            path='/index.html' if path=='/' else path
            files={'/index.html':('index.html','text/html'),'/app.css':('app.css','text/css'),'/app.js':('app.js','application/javascript'),'/collab.js':('collab.js','application/javascript'),'/print.js':('print.js','application/javascript'),'/favicon.svg':('favicon.svg','image/svg+xml')}
            if path not in files:return self.send(404,{'error':'No encontrado'})
            fname,typ=files[path];return self.send(200,(FRONT/fname).read_bytes(),typ)
        if path=='/health':return self.send(200,{'status':'ok','app':'VLUX Finanzas','storage':MODE,'environment':MODE_APP})
        db=DB()
        try:
            u=self.require(db)
            if path=='/api/me':data={'user':u,'mode':MODE_APP,'database':MODE}
            elif path=='/api/users':data={'users':get_users(db)}
            elif path=='/api/dashboard':data={'stats':compute_stats(db),'projects':get_projects(db)[:5],'transactions':get_transactions(db)[:8]}
            elif path=='/api/transactions':data={'transactions':get_transactions(db)}
            elif path=='/api/projects':data={'projects':get_projects(db),'project_stats':compute_stats(db)['by_project']}
            elif path=='/api/settings':data={'settings':get_settings(db)}
            elif path=='/api/forecast':data={'forecasts':db.rows('SELECT * FROM {forecasts} ORDER BY period'),'settings':get_settings(db),'stats':compute_stats(db)}
            elif path=='/api/compensations':
                c=db.rows('SELECT c.*,u.name AS person_name,creator.name AS creator_name FROM {compensations} c JOIN {users} u ON u.id=c.user_id JOIN {users} creator ON creator.id=c.created_by ORDER BY c.id DESC')
                data={'compensations':c,'users':get_users(db)}
            elif path=='/api/dividends':
                rows=db.rows('SELECT d.*,u.name AS creator_name FROM {dividends} d JOIN {users} u ON u.id=d.created_by ORDER BY d.id DESC')
                approval=db.rows('SELECT dividend_id,user_id FROM {dividend_approvals}')
                for d in rows:d['approvals']=[a['user_id'] for a in approval if a['dividend_id']==d['id']]
                data={'dividends':rows,'stats':compute_stats(db)}
            elif path=='/api/audit':
                data={'events':db.rows('SELECT a.*,u.name AS actor_name FROM {audit} a LEFT JOIN {users} u ON u.id=a.actor_id ORDER BY a.id DESC')[:300]}
            elif path.startswith('/api/collab/'):
                if re.fullmatch(r'/api/collab/receipts/\d+',path):
                    content=collab.render_receipt(db,int(path.split('/')[-1]))
                    return self.send(200,content.encode('utf-8'),'text/html')
                data=collab.get(db,path)
                if data is None:raise UserError('Módulo de colaboración no encontrado')
            elif path=='/api/export':
                from urllib.parse import parse_qs
                t=parse_qs(urlparse(self.path).query).get('type',['transactions'])[0]
                if t not in ('transactions','audit','projects'):raise UserError('Exportación desconocida')
                records=(get_transactions(db) if t=='transactions' else get_projects(db) if t=='projects' else db.rows('SELECT * FROM {audit} ORDER BY id DESC'))
                out=io.StringIO();w=csv.writer(out)
                if records:
                    keys=list(records[0].keys());w.writerow(keys)
                    for record in records:
                        # Avoid CSV formula injection in Excel.
                        w.writerow([("'"+str(record.get(k,'')) if str(record.get(k,'')).lstrip().startswith(('=','+','-','@')) else record.get(k,'')) for k in keys])
                return self.send(200,out.getvalue().encode('utf-8-sig'),'text/csv',[('Content-Disposition',f'attachment; filename="vlux_{t}.csv"')])
            else:return self.send(404,{'error':'Ruta inexistente'})
            self.send(200,data)
        except collab.CError as e:self.send(400,{'error':str(e)})
        except Forbidden as e:self.send(403,{'error':str(e)})
        except UserError as e:self.send(400,{'error':str(e)})
        except Exception as e:print('GET ERROR',repr(e),flush=True);self.send(500,{'error':'Error interno; revise registro del servidor'})
        finally:db.close()
    def do_POST(self):self.write_request('POST')
    def do_PUT(self):self.write_request('PUT')
    def write_request(self,method):
        path=urlparse(self.path).path
        db=DB()
        try:
            obj=self.body()
            if path=='/api/login':
                ip=self.client_address[0]
                with FAIL_LOCK:
                    attempts=[x for x in LOGIN_FAILS.get(ip,[]) if x>time.time()-300]
                    LOGIN_FAILS[ip]=attempts
                    if len(attempts)>=6:raise Forbidden('Demasiados intentos. Intente dentro de 5 minutos.')
                email=check_str(obj.get('email'),'correo',200).lower();pwd=check_str(obj.get('password'),'contraseña',500)
                u=db.one('SELECT * FROM {users} WHERE email=? AND active=1',(email,))
                if not u or not verify_pwd(pwd,u['password_hash']):
                    with FAIL_LOCK:LOGIN_FAILS.setdefault(ip,[]).append(time.time())
                    raise Forbidden('Correo o contraseña incorrectos')
                with FAIL_LOCK:LOGIN_FAILS.pop(ip,None)
                token=secrets.token_urlsafe(36)
                expiry=(datetime.now(timezone.utc)+timedelta(hours=10)).replace(microsecond=0).isoformat()
                db.insert('sessions',['user_id','token_hash','expires_at'],[u['id'],sha(token),expiry]);db.commit()
                return self.send(200,{'ok':True,'user':{'name':u['name'],'role':u['role']}},headers=[self.cookie(token,36000)])
            u=self.require(db,write=(path!='/api/logout' and path!='/api/change-password'))
            uid=u['id']
            if path=='/api/logout':
                cookie=self.headers.get('Cookie','')
                for part in cookie.split(';'):
                    if part.strip().startswith('vlux_session='):
                        db.execute('DELETE FROM {sessions} WHERE token_hash=?',(sha(part.strip().split('=',1)[1]),));break
                db.commit();return self.send(200,{'ok':True},headers=[self.cookie()])
            if path=='/api/change-password':
                pw=check_str(obj.get('current_password'),'contraseña actual',500)
                new=check_str(obj.get('new_password'),'contraseña nueva',500)
                if len(new)<12:raise UserError('La nueva contraseña debe tener al menos 12 caracteres')
                original=db.one('SELECT password_hash FROM {users} WHERE id=?',(uid,))
                if not verify_pwd(pw,original['password_hash']):raise Forbidden('Contraseña actual incorrecta')
                db.execute('UPDATE {users} SET password_hash=? WHERE id=?',(encode_pwd(new),uid))
                db.execute('DELETE FROM {sessions} WHERE user_id=?',(uid,))
                audit(db,uid,'PASSWORD_CHANGED','users',uid);db.commit()
                return self.send(200,{'ok':True},headers=[self.cookie()])
            if path.startswith('/api/collab/'):
                rid=collab.post(db,path,obj,u,audit,now)
            elif path=='/api/projects' and method=='POST':
                name=check_str(obj.get('name'),'proyecto',200);client=check_str(obj.get('client'),'cliente',200)
                budget=obj.get('budget_cents',0)
                if not isinstance(budget,int) or budget<0:raise UserError('Presupuesto no válido')
                status=obj.get('status','activo')
                if status not in ('activo','cotizado','pausado','cerrado'):raise UserError('Estado desconocido')
                rid=db.insert('projects',['name','client','budget_cents','status','created_at'],[name,client,budget,status,now()]);audit(db,uid,'CREATED','projects',rid,name)
            elif path.startswith('/api/projects/') and path.endswith('/status'):
                rid=self.path.split('/')[3]
                if not rid.isdecimal():raise UserError('ID inválido')
                state=obj.get('status')
                if state not in ('activo','cotizado','pausado','cerrado'):raise UserError('Estado inválido')
                if not db.one('SELECT id FROM {projects} WHERE id=?',(int(rid),)):raise UserError('Proyecto inexistente')
                db.execute('UPDATE {projects} SET status=? WHERE id=?',(state,int(rid)));audit(db,uid,'STATUS','projects',int(rid),state)
            elif path=='/api/transactions' and method=='POST':
                kind=obj.get('kind')
                if kind not in ('income','expense','capital'):raise UserError('Tipo de movimiento inválido')
                amount=cents(obj.get('amount_cents'))
                day=valid_date(obj.get('txn_date'))
                category=check_str(obj.get('category'),'categoría',100)
                description=check_str(obj.get('description'),'concepto',600)
                reference=check_str(obj.get('reference',''),'referencia',200,optional=True)
                project_id=obj.get('project_id') or None
                if project_id is not None and not db.one('SELECT id FROM {projects} WHERE id=?',(project_id,)):raise UserError('Proyecto no existe')
                state='pendiente' if ((kind=='expense' and amount>100000) or kind=='capital') else 'vigente'
                rid=db.insert('transactions',['txn_date','kind','amount_cents','category','description','project_id','recipient_user_id','reference','status','created_by','created_at'],[day,kind,amount,category,description,project_id,None,reference,state,uid,now()]);audit(db,uid,'CREATED','transactions',rid,f'{kind} {amount} centavos | {state} | {description[:120]}')
            elif re.fullmatch(r'/api/transactions/\d+/approve',path):
                rid=int(path.split('/')[3]);t=db.one('SELECT * FROM {transactions} WHERE id=?',(rid,))
                if not t or t['status']!='pendiente':raise UserError('No existe movimiento pendiente de autorización')
                if t['created_by']==uid:raise Forbidden('Sólo el otro socio puede autorizar el movimiento')
                updated=db.execute('UPDATE {transactions} SET status=? WHERE id=? AND status=?',('vigente',rid,'pendiente'))
                if updated.rowcount!=1:raise UserError('El movimiento ya fue autorizado')
                audit(db,uid,'APPROVED','transactions',rid,'Autorización dual financiera')
            elif path.startswith('/api/transactions/') and path.endswith('/void'):
                rid=self.path.split('/')[3]
                if not rid.isdecimal():raise UserError('ID inválido')
                reason=check_str(obj.get('reason'),'motivo de anulación',400)
                t=db.one('SELECT * FROM {transactions} WHERE id=?',(int(rid),))
                if not t or t['status'] not in ('vigente','pendiente'):raise UserError('Movimiento inexistente o ya anulado')
                if t['kind']=='distribution' or t['category'] in ('Remuneración a socio','Liquidación colaborador') or db.one('SELECT id FROM {project_costs} WHERE transaction_id=?',(int(rid),)) or db.one('SELECT id FROM {sale_collections} WHERE transaction_id=?',(int(rid),)):raise UserError('Pago formal no anulable aquí; se requiere ajuste documentado externo')
                db.execute('UPDATE {transactions} SET status=?,void_reason=? WHERE id=?',('anulado',reason,int(rid)))
                audit(db,uid,'VOIDED','transactions',int(rid),reason)
            elif path=='/api/compensations':
                person=int(obj.get('user_id',0));period=valid_period(obj.get('period'));amount=cents(obj.get('amount_cents'))
                person_rec=db.one('SELECT id,role,active FROM {users} WHERE id=?',(person,))
                if not person_rec or person_rec['role']!='socio' or not person_rec['active']:raise UserError('El beneficiario debe ser socio activo')
                if person != uid:raise UserError('Cada socio debe presentar su propia solicitud para permitir aprobación cruzada')
                note=check_str(obj.get('notes',''),'notas',600,True)
                rid=db.insert('compensations',['period','user_id','amount_cents','notes','state','created_by','created_at'],[period,person,amount,note,'solicitado',uid,now()]);audit(db,uid,'CREATED','compensations',rid,f'{period}; {person}; {amount} centavos')
            elif re.fullmatch(r'/api/compensations/\d+/(approve|pay)',path):
                _,_,rid,action=path.split('/')[-4:]
                rid=int(rid);c=db.one('SELECT * FROM {compensations} WHERE id=?',(rid,))
                if not c:raise UserError('Solicitud no existe')
                if action=='approve':
                    if c['state']!='solicitado':raise UserError('Estado no permite autorizar')
                    if c['created_by']==uid or c['user_id']==uid:raise Forbidden('Debe aprobar el otro socio (no el solicitante ni el beneficiario)')
                    db.execute('UPDATE {compensations} SET state=?,approved_by=? WHERE id=?',('aprobado',uid,rid));audit(db,uid,'APPROVED','compensations',rid)
                else:
                    if c['state']!='aprobado':raise UserError('Primero necesita aprobación')
                    if compute_stats(db)['balance_cents']<c['amount_cents']:raise UserError('Caja insuficiente para pagar la remuneración')
                    updated=db.execute('UPDATE {compensations} SET state=?,paid_by=? WHERE id=? AND state=?',('pagado',uid,rid,'aprobado'))
                    if updated.rowcount!=1:raise UserError('La remuneración ya fue procesada')
                    tx=db.insert('transactions',['txn_date','kind','amount_cents','category','description','project_id','recipient_user_id','reference','status','created_by','created_at'],[iso_today(),'expense',c['amount_cents'],'Remuneración a socio','Remuneración '+c['period'],None,c['user_id'],'REM-'+str(rid),'vigente',uid,now()])
                    db.execute('UPDATE {compensations} SET transaction_id=? WHERE id=?',(tx,rid));audit(db,uid,'PAID','compensations',rid,f'transaction {tx}')
            elif path=='/api/dividends':
                period=check_str(obj.get('period'),'periodo',20)
                if not re.fullmatch(r'20\d\d-Q[1-4]',period):raise UserError('Periodo: 2026-Q4')
                amount=cents(obj.get('amount_cents'))
                accounting_ref=check_str(obj.get('accounting_reference',''),'referencia contable',300,True)
                st=compute_stats(db)
                if st['pending_approvals']>0:raise UserError('Primero deben atender los movimientos pendientes de aprobación')
                reserved_proposals=db.one("SELECT COALESCE(SUM(amount_cents),0) AS n FROM {dividends} WHERE state IN ('propuesto','aprobado')")['n']
                if st['candidate_dividend_capacity_cents']-int(reserved_proposals)<amount:raise UserError('La propuesta supera el 30% de utilidad estimada disponible después de provisión de planeación')
                if st['operating_profit_cents']-st['distribution_cents']<amount or st['free_cash_cents']<amount:raise UserError('La utilidad remanente o caja libre no permite proponer el reparto')
                rid=db.insert('dividends',['period','amount_cents','state','accounting_reference','created_by','created_at'],[period,amount,'propuesto',accounting_ref,uid,now()]);audit(db,uid,'CREATED','dividends',rid,f'{period}; {amount} centavos')
            elif re.fullmatch(r'/api/dividends/\d+/(approve|pay)',path):
                parts=path.split('/');rid=int(parts[3]);action=parts[4]
                d=db.one('SELECT * FROM {dividends} WHERE id=?',(rid,))
                if not d:raise UserError('Propuesta no encontrada')
                socios=db.rows("SELECT id FROM {users} WHERE role='socio' AND active=1")
                if len(socios)!=2:raise UserError('Se requieren exactamente 2 socios activos para el reparto 50/50 de esta versión')
                if action=='approve':
                    if d['state'] not in ('propuesto','aprobado'):raise UserError('Estado no permite aprobar')
                    if not db.one('SELECT id FROM {dividend_approvals} WHERE dividend_id=? AND user_id=?',(rid,uid)):
                        db.insert('dividend_approvals',['dividend_id','user_id','created_at'],[rid,uid,now()]);audit(db,uid,'APPROVED','dividends',rid)
                    n=db.one('SELECT COUNT(*) AS n FROM {dividend_approvals} WHERE dividend_id=?',(rid,))['n']
                    if n>=2:db.execute('UPDATE {dividends} SET state=? WHERE id=?',('aprobado',rid))
                else:
                    if d['state']!='aprobado':raise UserError('Necesita autorización de ambos socios')
                    ref=check_str(obj.get('accounting_reference') or d['accounting_reference'],'referencia de acta y validación contable',300)
                    st=compute_stats(db)
                    if st['pending_approvals']>0:raise UserError('Existen movimientos pendientes de aprobación')
                    if st['free_cash_cents']<d['amount_cents']:raise UserError('La reserva mínima o la caja disponible impide el pago')
                    if st['candidate_dividend_capacity_cents']<d['amount_cents']:raise UserError('El tope interno del 30% de utilidad neta estimada impide el pago')
                    if st['operating_profit_cents']-st['distribution_cents']<d['amount_cents']:raise UserError('Utilidades remanentes insuficientes')
                    updated=db.execute('UPDATE {dividends} SET state=?,paid_by=?,accounting_reference=? WHERE id=? AND state=?',('pagado',uid,ref,rid,'aprobado'))
                    if updated.rowcount!=1:raise UserError('La distribución ya fue procesada')
                    # Check other approved payouts separately as reserve protection via balance.
                    half=d['amount_cents']//2
                    for index,person in enumerate(socios):
                        val=half if index==0 else d['amount_cents']-half
                        tx=db.insert('transactions',['txn_date','kind','amount_cents','category','description','project_id','recipient_user_id','reference','status','created_by','created_at'],[iso_today(),'distribution',val,'Distribución a accionistas','Dividendo '+d['period'],None,person['id'],'DIV-'+str(rid)+'; '+ref,'vigente',uid,now()])
                        audit(db,uid,'DIVIDEND_PAYMENT','transactions',tx,f'Beneficiario {person["id"]}, bruto {val}')
                    audit(db,uid,'PAID','dividends',rid,ref)
            elif path=='/api/forecast' and method=='PUT':
                period=valid_period(obj.get('period'))
                val=obj.get('revenue_cents')
                if not isinstance(val,int) or isinstance(val,bool) or val<0 or val>100_000_000_000:raise UserError('Ingreso estimado inválido')
                notes=check_str(obj.get('notes',''),'notas',300,True)
                if db.one('SELECT period FROM {forecasts} WHERE period=?',(period,)):
                    db.execute('UPDATE {forecasts} SET revenue_cents=?,notes=?,updated_by=?,updated_at=? WHERE period=?',(val,notes,uid,now(),period))
                else:db.insert('forecasts',['period','revenue_cents','notes','updated_by','updated_at'],[period,val,notes,uid,now()])
                audit(db,uid,'UPDATED','forecasts',None,f'{period}: {val} centavos')
                rid=None
            elif path=='/api/settings' and method=='PUT':
                for k, v in obj.items():
                    if k not in DEFAULT_SETTINGS or not isinstance(DEFAULT_SETTINGS[k],int):raise UserError(f'Parámetro no permitido: {k}')
                    if not isinstance(v,int) or isinstance(v,bool) or v<0 or v>1_000_000_000:raise UserError(f'Valor incorrecto: {k}')
                    if k.endswith('_pct') and v>100:raise UserError('Porcentaje máximo 100')
                    if k.startswith('share_') and v!=50:raise UserError('Esta versión conserva la participación contractual 50/50')
                    if k=='variable_cost_pct' and v>=100:raise UserError('Costos variables deben ser menores al 100%')
                    db.execute('UPDATE {settings} SET {value}=? WHERE {key}=?',(str(v),k))
                audit(db,uid,'UPDATED','settings',None,', '.join(obj.keys()))
                rid=None
            elif path=='/api/users':
                name=check_str(obj.get('name'),'nombre',200);email=check_str(obj.get('email'),'email',200).lower();pwd=check_str(obj.get('password'),'contraseña',200)
                role=obj.get('role','consulta')
                if role!='consulta':raise UserError('Para incorporar socios se requiere formalización societaria; desde aquí sólo pueden crearse lectores')
                if '@' not in email or len(pwd)<12:raise UserError('Correo válido y contraseña de 12+ caracteres obligatorios')
                if db.one('SELECT id FROM {users} WHERE email=?',(email,)):raise UserError('Ya existe ese correo')
                rid=db.insert('users',['name','email','password_hash','role','active','created_at'],[name,email,encode_pwd(pwd),role,1,now()]);audit(db,uid,'CREATED','users',rid,name)
            else:return self.send(404,{'error':'Operación inexistente'})
            db.commit();self.send(200,{'ok':True,'id':rid if 'rid' in locals() else None})
        except collab.CError as e:db.rollback();self.send(400,{'error':str(e)})
        except Forbidden as e:db.rollback();self.send(403,{'error':str(e)})
        except UserError as e:db.rollback();self.send(400,{'error':str(e)})
        except Exception as e:
            db.rollback();print('POST ERROR',repr(e),flush=True);self.send(500,{'error':'Error interno; consulte el servidor'})
        finally:db.close()

def open_local_desktop():
    """Launch an app-mode browser only after the HTTP server is listening."""
    if os.getenv('VLUX_OPEN_BROWSER') != '1' or os.name != 'nt':
        return
    url = f'http://127.0.0.1:{PORT}'
    program_dirs = [os.environ.get('PROGRAMFILES(X86)'),os.environ.get('PROGRAMFILES')]
    edge = next((Path(d) / 'Microsoft' / 'Edge' / 'Application' / 'msedge.exe'
                 for d in program_dirs if d and (Path(d) / 'Microsoft' / 'Edge' / 'Application' / 'msedge.exe').is_file()),None)
    try:
        if edge:
            subprocess.Popen([str(edge),'--app='+url,'--window-size=1440,900'],
                             stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        else:
            import webbrowser
            webbrowser.open(url)
            print('Microsoft Edge no encontrado; abriendo el navegador predeterminado.',flush=True)
    except Exception as exc:
        print(f'No pude abrir navegador automaticamente: {exc}. Abre {url}',flush=True)

if __name__=='__main__':
    try:bootstrap()
    except Exception as e:print('FALLO DE INICIO:',str(e),file=sys.stderr);sys.exit(1)
    try:
        server=ThreadingHTTPServer((HOST,PORT),Handler)
    except OSError as exc:
        print(f'FALLO DE PUERTO {HOST}:{PORT}: {exc}',file=sys.stderr)
        print('Si otra instancia de VLUX esta abierta, cierrala antes de iniciar una nueva.',file=sys.stderr)
        sys.exit(1)
    print(f'VLUX Finanzas {MODE_APP} · {MODE} · http://{HOST}:{PORT}',flush=True)
    open_local_desktop()
    try:server.serve_forever()
    except KeyboardInterrupt:print('Servidor detenido.')
    finally:server.server_close()
