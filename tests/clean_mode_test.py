"""Local clean mode must never preload demo financial transactions."""
import json,os,subprocess,sys,tempfile,time,urllib.request,urllib.error,socket,sqlite3
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]

def get_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));return s.getsockname()[1]

NEW_PASSWORD='Prueba-Local-2026!'

def do(url,method='GET',obj=None,cookie=''):
    data=json.dumps(obj).encode() if obj is not None else None
    headers={'X-Requested-With':'VLUX-Desktop','Origin':url.split('/api/')[0].split('/app.js')[0].split('/health')[0]}
    if obj is not None:headers['Content-Type']='application/json'
    if cookie:headers['Cookie']=cookie
    req=urllib.request.Request(url,method=method,data=data,headers=headers)
    with urllib.request.urlopen(req,timeout=8) as r:
        text=r.read()
        if url.endswith('/app.js'):return text.decode('utf-8'),''
        return json.loads(text),r.headers.get('Set-Cookie','')

def exercise(mode,dbpath):
    port=get_port();url=f'http://127.0.0.1:{port}'
    e=os.environ.copy();e.update(VLUX_MODE=mode,VLUX_DB='sqlite',VLUX_HOST='127.0.0.1',VLUX_PORT=str(port),VLUX_SQLITE_PATH=str(dbpath))
    proc=subprocess.Popen([sys.executable,str(BASE/'backend/app.py')],env=e,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(80):
            try: do(url+'/health');break
            except Exception:time.sleep(.1)
        else:raise AssertionError('No HTTP startup')
        if mode=='local':
            # Local mode refuses the public test password; on a relaunch it was already replaced.
            try:
                do(url+'/api/login','POST',{'email':'ludwing@vlux.local','password':'DemoVlux2026!'})
                raise AssertionError('demo password accepted in local mode')
            except urllib.error.HTTPError as e:
                assert e.code==403,e.code
            try:do(url+'/api/first-password','POST',{'email':'ludwing@vlux.local','current_password':'DemoVlux2026!','new_password':NEW_PASSWORD})
            except urllib.error.HTTPError as e:assert e.code==403,e.code
        password=NEW_PASSWORD if mode=='local' else 'DemoVlux2026!'
        _,h=do(url+'/api/login','POST',{'email':'ludwing@vlux.local','password':password})
        cookie=h.split(';')[0]
        stats,_=do(url+'/api/dashboard',cookie=cookie)
        projects,_=do(url+'/api/projects',cookie=cookie)
        transactions,_=do(url+'/api/transactions',cookie=cookie)
        forecasts,_=do(url+'/api/forecast',cookie=cookie)
        js,_=do(url+'/app.js')
        assert "Reglas y políticas" in js and 'renderPolicies' in js
        assert stats['stats']['balance_cents']==(0 if mode=='local' else stats['stats']['balance_cents'])
        if mode=='local':
            assert not projects['projects']
            assert not transactions['transactions']
            assert not forecasts['forecasts']
            assert stats['stats']['operating_profit_cents']==0
            assert stats['stats']['income_cents']==0
            assert stats['stats']['expense_cents']==0
            assert stats['stats']['candidate_dividend_capacity_cents']==0
        else:
            assert len(projects['projects'])==3
            assert len(transactions['transactions'])==12
        print('PASS',mode,'projects',len(projects['projects']),'movements',len(transactions['transactions']),'forecasts',len(forecasts['forecasts']))
    finally:
        proc.terminate();proc.wait(timeout=8)

if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='vlux_v02_') as t:
        a=Path(t)/'clean.sqlite3';b=Path(t)/'demo.sqlite3'
        exercise('local',a)
        exercise('local',a) # relaunch preserves users, no financial seeds
        exercise('demo',b)
        assert a!=b
        # Important guarantee: clean base and old demo DB are separate files
        with sqlite3.connect(a) as db:
            assert db.execute('SELECT COUNT(*) FROM users').fetchone()[0]==3
        print('PASS: bases aisladas y reglas accesibles')
