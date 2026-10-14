"""Integration tests: starts isolated SQLite demo on ephemeral local port, no third-party packages."""
import json,os,subprocess,sys,tempfile,time,urllib.request,urllib.error,socket
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
with socket.socket() as a:a.bind(('127.0.0.1',0));PORT=a.getsockname()[1]
BASE_URL=f'http://127.0.0.1:{PORT}'

def req(path,verb='GET',data=None,cookie='',ok=True):
    h={'X-Requested-With':'VLUX-Desktop','Origin':BASE_URL}
    if cookie:h['Cookie']=cookie
    b=json.dumps(data).encode() if data is not None else None
    if b:h['Content-Type']='application/json'
    request=urllib.request.Request(BASE_URL+path,method=verb,data=b,headers=h)
    try:
        with urllib.request.urlopen(request,timeout=12) as r:
            ret=json.loads(r.read());status=r.status;setcookie=r.headers.get('Set-Cookie','')
    except urllib.error.HTTPError as e:
        status=e.code;ret=json.loads(e.read());setcookie=''
    if ok!=(status==200):raise AssertionError((path,status,ret))
    return ret,setcookie

def main():
 with tempfile.TemporaryDirectory(prefix='vlux_test_') as tmp:
    env=os.environ.copy();env.update(VLUX_PORT=str(PORT),VLUX_HOST='127.0.0.1',VLUX_DB='sqlite',VLUX_MODE='demo',VLUX_SQLITE_PATH=str(Path(tmp)/'qa.sqlite3'))
    p=subprocess.Popen([sys.executable,str(BASE/'backend/app.py')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                req('/health');break
            except Exception:time.sleep(.12)
        else:raise AssertionError('API no inició')
        def login(email):
            _,cookie=req('/api/login','POST',{'email':email,'password':'DemoVlux2026!'})
            return cookie.split(';')[0]
        l,r,v=[login(x+'@vlux.local') for x in ('ludwing','rodrigo','consulta')]
        req('/api/dashboard',ok=False)
        req('/api/projects','POST',{'name':'Fail','client':'Fail','budget_cents':1},v,False)
        pjt,_=req('/api/projects','POST',{'name':'Test','client':'Test Co','budget_cents':1500000},l)
        pid=pjt['id']
        req('/api/forecast','PUT',{'period':'2027-01','revenue_cents':9900000},l)
        fc,_=req('/api/forecast',cookie=l)
        assert next(f for f in fc['forecasts'] if f['period']=='2027-01')['revenue_cents']==9900000
        mov,_=req('/api/transactions','POST',{'txn_date':'2026-10-10','kind':'expense','amount_cents':250000,'category':'Equipo','description':'Equipo QA','project_id':pid},l)
        tid=mov['id']
        t,_=req('/api/transactions',cookie=l)
        assert next(x for x in t['transactions'] if x['id']==tid)['status']=='pendiente'
        req('/api/transactions/'+str(tid)+'/approve','POST',{},l,False)
        req('/api/transactions/'+str(tid)+'/approve','POST',{},r)
        comp,_=req('/api/compensations','POST',{'user_id':1,'period':'2026-10','amount_cents':600000},l)
        req('/api/compensations/'+str(comp['id'])+'/approve','POST',{},r)
        req('/api/compensations/'+str(comp['id'])+'/pay','POST',{},l)
        req('/api/compensations/'+str(comp['id'])+'/pay','POST',{},l,False)
        dividend,_=req('/api/dividends','POST',{'period':'2026-Q4','amount_cents':500000,'accounting_reference':'Control test'},l)
        did=str(dividend['id'])
        req('/api/dividends/'+did+'/approve','POST',{},l)
        req('/api/dividends/'+did+'/pay','POST',{'accounting_reference':'Acta y contador QA'},l,False)
        req('/api/dividends/'+did+'/approve','POST',{},r)
        req('/api/dividends/'+did+'/pay','POST',{'accounting_reference':'Acta y contador QA'},r)
        stats,_=req('/api/dashboard',cookie=r)
        assert stats['stats']['distribution_cents']==500000
        assert 'forecast' not in stats
        req('/api/settings','PUT',{'reserve_target_cents':2000000},v,False)
        print('PASS: autenticación, roles, movimientos, doble aprobación, remuneraciones, dividendos, proyección, reserva, protección doble pago')
    finally:
        p.terminate()
        p.wait(timeout=8)
if __name__=='__main__':main()
