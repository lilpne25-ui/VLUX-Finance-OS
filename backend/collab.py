"""VLUX collaborator settlements V0.3: per-sale basis, dual reviewed expenses, and audited disbursements.
Important: a calculated proposal is not an authorization to pay.
"""
import hashlib, html, json, re
from datetime import date,datetime,timedelta

class CError(Exception):pass

def required(s,label,size=300):
    if not isinstance(s,str) or not s.strip() or len(s)>size:raise CError(f'{label}: dato obligatorio o demasiado largo')
    return s.strip()

def positive(v):
    if type(v) is not int or v<=0 or v>200_000_000_000:raise CError('Importe en centavos inválido')
    return v

def day(v):
    try:return date.fromisoformat(required(v,'fecha',10)).isoformat()
    except ValueError:raise CError('Fecha inválida')

def period(v):
    if not isinstance(v,str) or not re.fullmatch(r'20\d\d-(0[1-9]|1[0-2])',v):raise CError('Periodo AAAA-MM inválido')
    return v

def found(db,table,id):
    if type(id) is not int or id<=0:raise CError('Identificador inválido')
    r=db.one(f'SELECT * FROM {{{table}}} WHERE id=?',(id,))
    if not r:raise CError(f'Registro de {table} no encontrado')
    return r

def add_workdays(base, n):
    d=base
    while n>0:
        d+=timedelta(days=1)
        if d.weekday()<5:n-=1
    return d

def cents_mx(n):return f'${n/100:,.2f} MXN'

def seed(db):
    """Create neutral collaborator profiles. Private contract terms must be entered by authorized partners."""
    if db.one('SELECT COUNT(*) n FROM {collaborators}')['n']:return
    people=[
      ('Colaborador de desarrollo','Desarrollo e implementaciones','Perfil de ejemplo. Agrega el contrato vigente antes de activar participaciones.'),
      ('Colaborador de producto','Colaboración técnica y funcional','Perfil de ejemplo. El acuerdo debe revisarse y cargarse en forma privada.'),
      ('Colaborador comercial','Prospección, cierre y ventas','Perfil de ejemplo. Ningún porcentaje queda autorizado por defecto.')]
    for name,specialty,notes in people:
        db.insert('collaborators',['name','specialty','notes','active'],[name,specialty,notes,1])
    db.commit()

def list_all(db):
    collaborators=db.rows('SELECT * FROM {collaborators} ORDER BY id')
    terms=db.rows('SELECT t.*,c.name collaborator_name FROM {collab_terms} t JOIN {collaborators} c ON c.id=t.collaborator_id ORDER BY t.id')
    for t in terms:t['votes']=db.one('SELECT COUNT(*) n FROM {term_approvals} WHERE term_id=?',(t['id'],))['n']
    return {'collaborators':collaborators,'terms':terms}

def sales_data(db):
    rs=db.rows('SELECT s.*,p.name project_name,p.client client_name FROM {sales} s JOIN {projects} p ON p.id=s.project_id ORDER BY s.id DESC')
    for s in rs:
        q=financials(db,s['id'])
        s.update({k:q[k] for k in ('collected_cents','costs_cents','available_base_cents','unallocated_cents','review_votes','fingerprint','unpaid_costs','due_recurring')})
    return rs

def approved_receipts(db,sale_id):
    return db.rows("SELECT c.*,t.status transaction_status FROM {sale_collections} c JOIN {transactions} t ON t.id=c.transaction_id WHERE c.sale_id=? ORDER BY c.collection_date,c.id",(sale_id,))

def expense_rows(db,sale_id):
    return db.rows('SELECT c.*,t.status transaction_status FROM {project_costs} c LEFT JOIN {transactions} t ON t.id=c.transaction_id WHERE c.sale_id=? ORDER BY c.id',(sale_id,))

def financials(db,sale_id):
    s=found(db,'sales',sale_id)
    receipts=approved_receipts(db,sale_id)
    costs=expense_rows(db,sale_id)
    collected=sum(int(x['amount_cents']) for x in receipts if x['transaction_status']=='vigente')
    spent=sum(int(x['amount_cents']) for x in costs if x['transaction_status']=='vigente' and x['status']=='pagado')
    # Expenses created through the legacy Movimientos tab are not implicitly attributable to a specific sale.
    unallocated=db.one('''SELECT COALESCE(SUM(t.amount_cents),0) n FROM {transactions} t
      WHERE t.project_id=? AND t.kind='expense' AND t.category NOT IN ('Liquidación colaborador','Remuneración a socio') AND t.status IN ('vigente','pendiente')
      AND t.id NOT IN (SELECT transaction_id FROM {project_costs} WHERE transaction_id IS NOT NULL)''',(s['project_id'],))['n']
    unpaid_costs=sum(1 for x in costs if x['status']!='pagado' or x['transaction_status']!='vigente')
    schedules=db.rows('SELECT * FROM {recurring_costs} WHERE sale_id=? AND active=1',(sale_id,))
    due=[x for x in schedules if x['next_due']<=date.today().isoformat()]
    snapshot={'sale':sale_id,'total':s['net_total_cents'],'receipts':[(x['id'],x['amount_cents'],x['transaction_status']) for x in receipts],
              'costs':[(x['id'],x['amount_cents'],x['transaction_status'],x['status']) for x in costs],
              'unallocated':unallocated,'due':[(x['id'],x['next_due']) for x in due]}
    fingerprint=hashlib.sha256(json.dumps(snapshot,sort_keys=True).encode()).hexdigest()
    review_votes=db.one('SELECT COUNT(*) n FROM {cost_reviews} WHERE sale_id=? AND fingerprint=?',(sale_id,fingerprint))['n']
    return {'sale':s,'receipts':receipts,'costs':costs,'collected_cents':collected,'costs_cents':spent,
      'available_base_cents':max(0,collected-spent),'unallocated_cents':int(unallocated),'review_votes':int(review_votes),
      'unpaid_costs':unpaid_costs,'due_recurring':due,'fingerprint':fingerprint,'schedules':schedules}

def assignment_data(db):
    sql='''SELECT a.*,c.name collaborator_name,t.title term_title,t.code term_code,t.version term_version,t.rate_bp,t.trigger_kind,t.active term_active,
      t.source_status,t.scope,t.notes term_notes,s.label sale_label,s.project_id,p.name project_name
      FROM {assignments} a JOIN {collaborators} c ON c.id=a.collaborator_id
      JOIN {collab_terms} t ON t.id=a.term_id JOIN {sales} s ON s.id=a.sale_id JOIN {projects} p ON p.id=s.project_id ORDER BY a.id DESC'''
    result=db.rows(sql)
    for x in result:
        x['estimate']=estimate(db,x['id'])
    return result

def estimate(db,aid):
    a=found(db,'assignments',aid); t=found(db,'collab_terms',a['term_id']);f=financials(db,a['sale_id'])
    r=[];s=f['sale']
    if not t['active']:r.append('Contrato no activado por ambos socios con evidencia firmada')
    if not a['delivered']:r.append('Falta registrar evidencia de trabajo/cierre realizado')
    if f['review_votes']<2:r.append('Falta revisión dual de costos y cobros')
    if f['unallocated_cents']>0:r.append('Existen gastos del proyecto sin asignar a una venta')
    if f['unpaid_costs']:r.append('Hay costos asignados pendientes de pago o aprobación')
    if f['due_recurring']:r.append('Existen costos recurrentes vencidos sin registrar')
    if f['collected_cents']<=0:r.append('No existen cobros confirmados')
    if t['trigger_kind']=='mariano_full' and f['collected_cents']<s['net_total_cents']:r.append('La modalidad comercial requiere pago TOTAL del cliente')
    if t['code']=='MA-BONUS' and not a['evidence']:r.append('Falta evidencia del aporte técnico adicional')
    if t['code']=='EN-DER':r.append('Revisión legal obligatoria: modalidad de versión derivada y plazo de 36 meses')
    if t['code']=='EN-POST':r.append('Revisión legal obligatoria: modalidad posterior a terminación')
    prior=db.one("SELECT COALESCE(SUM(amount_cents),0) n FROM {settlements} WHERE assignment_id=? AND state IN ('propuesto','aprobado','pagado')",(aid,))['n']
    eligible_total=(f['available_base_cents']*int(t['rate_bp']))//10000
    outstanding=max(0,eligible_total-int(prior))
    if outstanding<=0:r.append('Sin monto nuevo disponible; ya propuesto, aprobado o liquidado')
    sibling=db.rows('SELECT a.id,t.code FROM {assignments} a JOIN {collab_terms} t ON t.id=a.term_id WHERE a.sale_id=? AND a.collaborator_id=? AND a.id<>?',(a['sale_id'],a['collaborator_id'],aid))
    if sibling:r.append('Hay más de una modalidad para el mismo colaborador y venta; revisar duplicidad')
    # Potential 100% cap for simultaneous collaborators, excluding alternative duplications.
    combo=db.one('SELECT COALESCE(SUM(t.rate_bp),0) n FROM {assignments} a JOIN {collab_terms} t ON t.id=a.term_id WHERE a.sale_id=?',(a['sale_id'],))['n']
    if combo>10000:r.append('Porcentajes totales de colaboradores exceden el 100% del margen')
    return {'base_cents':f['available_base_cents'],'rate_bp':t['rate_bp'],'earned_total_cents':eligible_total,'already_reserved_cents':int(prior),
       'candidate_cents':outstanding,'blockers':r,'eligible':not r,'fingerprint':f['fingerprint'],'collected_cents':f['collected_cents'],'expenses_cents':f['costs_cents']}

def render_receipt(db,id):
    v=found(db,'settlements',id)
    a=found(db,'assignments',v['assignment_id']);t=found(db,'collab_terms',a['term_id']);c=found(db,'collaborators',a['collaborator_id']);f=financials(db,a['sale_id']);s=f['sale'];p=found(db,'projects',s['project_id'])
    esc=lambda s:html.escape(str(s))
    costs=''.join(f'<tr><td>{esc(x["category"])} — {esc(x["description"])}</td><td>{cents_mx(x["amount_cents"])}</td><td>{esc(x["status"])}</td></tr>' for x in f['costs']) or '<tr><td colspan="3">Sin costos documentados en la venta</td></tr>'
    state={'propuesto':'PROPUESTA — NO PAGADO','aprobado':'APROBADO — NO PAGADO','pagado':'PAGADO SEGÚN REGISTRO'}.get(v['state'],v['state'])
    return f'''<!doctype html><html lang="es"><meta charset="utf-8"><title>VLUX · Comprobante {id}</title><style>
    body{{font-family:Arial,sans-serif;background:#f5f6f9;color:#111827;margin:30px auto;max-width:850px;line-height:1.6}}article{{background:white;padding:45px;border-radius:16px}}h1{{letter-spacing:.12em}}small{{color:#64748b}}table{{width:100%;border-collapse:collapse;margin:18px 0}}td,th{{border-bottom:1px solid #ddd;text-align:left;padding:10px}}b{{color:#0d9488}}.total{{font-size:28px;font-weight:bold}}.status{{border:1px solid #ccc;padding:8px 12px;border-radius:6px}}@media print{{body{{background:white;margin:0}}article{{padding:10px}}button{{display:none}}}}</style>
    <article><h1>VLUX <small>FINANCE OS</small></h1><p><strong>Desglose de participación — Folio VLUX-CP-{id:06d}</strong></p><p class="status">{esc(state)}</p>
    <table><tr><th>Beneficiario</th><td>{esc(c['name'])}</td></tr><tr><th>Proyecto / venta</th><td>{esc(p['name'])} / {esc(s['label'])}</td></tr><tr><th>Trabajo realizado</th><td>{esc(a['task'])}</td></tr><tr><th>Convenio</th><td>{esc(t['title'])}, {esc(t['version'])}</td></tr><tr><th>Periodo</th><td>{esc(v['period'])}</td></tr><tr><th>Referencia de pago</th><td>{esc(v['voucher_reference'] or 'Sin registro')}</td></tr></table>
    <h3>Movimiento económico de la venta</h3><table><tr><td>Venta neta acordada (sin IVA)</td><td>{cents_mx(s['net_total_cents'])}</td></tr><tr><td>Cobros registrados netos (sin IVA)</td><td>{cents_mx(f['collected_cents'])}</td></tr><tr><td>Costos directos pagados documentados</td><td>− {cents_mx(f['costs_cents'])}</td></tr><tr><td>Base al momento del corte</td><td>{cents_mx(v['base_cents'])}</td></tr><tr><td>Porcentaje pactado de la modalidad</td><td>{v['rate_bp']/100:g}%</td></tr></table>
    <h3>Gastos aplicados registrados</h3><table><tr><th>Concepto</th><th>MXN</th><th>Estado</th></tr>{costs}</table><p class="total">Importe de este corte: {cents_mx(v['amount_cents'])}</p>
    <p><small>Documento de control interno. Si no figura como pagado, NO es comprobante de transferencia ni recibo fiscal. La base es comercial/contractual, no sustituye CFDI, cálculo de impuestos o conciliación bancaria. Los importes corresponden al snapshot de propuesta y los gastos mostrados son el desglose actual.</small></p>
    <button id="printTicket">Imprimir / Guardar como PDF</button></article><script src="/print.js"></script></html>'''

def get(db,path):
    if path=='/api/collab/people':return list_all(db)
    if path=='/api/collab/sales':return {'sales':sales_data(db)}
    if path=='/api/collab/assignments':return {'assignments':assignment_data(db)}
    if path=='/api/collab/costs':return {'costs':db.rows('SELECT c.*,p.name project_name,s.label sale_label,t.status txn_status FROM {project_costs} c JOIN {projects} p ON p.id=c.project_id JOIN {sales} s ON s.id=c.sale_id LEFT JOIN {transactions} t ON t.id=c.transaction_id ORDER BY c.id DESC'),'recurring':db.rows('SELECT r.*,p.name project_name,s.label sale_label FROM {recurring_costs} r JOIN {projects} p ON p.id=r.project_id JOIN {sales} s ON s.id=r.sale_id ORDER BY r.id DESC')}
    if path=='/api/collab/settlements':
        rows=db.rows('''SELECT l.*,c.name collaborator_name,s.label sale_label,p.name project_name,t.title term_title,a.task task,
          t.trigger_kind,doc.document_reference,doc.received_on,doc.due_on
          FROM {settlements} l JOIN {assignments} a ON a.id=l.assignment_id JOIN {collaborators} c ON c.id=a.collaborator_id
          JOIN {sales} s ON s.id=a.sale_id JOIN {projects} p ON p.id=s.project_id JOIN {collab_terms} t ON t.id=a.term_id
          LEFT JOIN {settlement_documents} doc ON doc.settlement_id=l.id ORDER BY l.id DESC''')
        for v in rows:
            if v['trigger_kind']=='enrique_monthly':
                y,m=map(int,v['period'].split('-'))
                if m==12:y+=1;m=1
                else:m+=1
                cut=date(y,m,1)-timedelta(days=1)
                v['statement_due_on']=add_workdays(cut,10).isoformat()
            else:v['statement_due_on']=None
        return {'settlements':rows}
    return None

def post(db,path,obj,u,audit,now):
    uid=u['id']
    if u['role']!='socio':raise CError('Solo socios autorizados pueden modificar datos')
    if path=='/api/collab/people':
        name=required(obj.get('name'),'nombre',200);role=required(obj.get('specialty'),'actividad',300)
        if db.one('SELECT id FROM {collaborators} WHERE name=?',(name,)):raise CError('Este colaborador ya está registrado')
        rid=db.insert('collaborators',['name','specialty','notes'],[name,role,str(obj.get('notes',''))[:600]])
        audit(db,uid,'CREATED','collaborators',rid,name);return rid
    if path=='/api/collab/terms':
        c=found(db,'collaborators',obj.get('collaborator_id'))
        rate=obj.get('rate_bp');code=required(obj.get('code'),'código',80)
        if type(rate) is not int or not 0<rate<=10000:raise CError('Porcentaje inválido')
        if db.one('SELECT id FROM {collab_terms} WHERE collaborator_id=? AND code=? AND version=?',(c['id'],code,obj.get('version'))):raise CError('Versión de acuerdo existente')
        rid=db.insert('collab_terms',['collaborator_id','title','code','version','rate_bp','trigger_kind','scope','document_url','source_status','notes','active'],
         [c['id'],required(obj.get('title'),'modalidad',200),code,required(obj.get('version'),'versión',60),rate,'manual_review',required(obj.get('scope'),'alcance',250),str(obj.get('document_url',''))[:600],'pendiente_firma',str(obj.get('notes',''))[:1200],0])
        audit(db,uid,'CREATED','collab_terms',rid,code);return rid
    if m:=re.fullmatch(r'/api/collab/terms/(\d+)/approve',path):
        rid=int(m[1]);term=found(db,'collab_terms',rid)
        ref=required(obj.get('signed_reference'),'referencia del contrato firmado',300)
        if not db.one('SELECT id FROM {term_approvals} WHERE term_id=? AND user_id=?',(rid,uid)):
            db.insert('term_approvals',['term_id','user_id','signed_reference','created_at'],[rid,uid,ref,now()])
        else:db.execute('UPDATE {term_approvals} SET signed_reference=?,created_at=? WHERE term_id=? AND user_id=?',(ref,now(),rid,uid))
        approvals=db.rows('SELECT * FROM {term_approvals} WHERE term_id=?',(rid,))
        if len(approvals)>=2:
            refs={a['signed_reference'] for a in approvals}
            if len(refs)==1:db.execute('UPDATE {collab_terms} SET active=1,source_status=?,signed_reference=? WHERE id=?',('documento_validado_internamente',ref,rid))
        audit(db,uid,'TERM_REVIEW','collab_terms',rid,ref);return rid
    if path=='/api/collab/sales':
        proj=found(db,'projects',obj.get('project_id'))
        rid=db.insert('sales',['project_id','label','net_total_cents','sales_date','created_by','created_at'],
            [proj['id'],required(obj.get('label'),'venta o contrato',200),positive(obj.get('net_total_cents')),day(obj.get('sales_date')),uid,now()])
        audit(db,uid,'CREATED','sales',rid,proj['name']);return rid
    if m:=re.fullmatch(r'/api/collab/sales/(\d+)/collect',path):
        sid=int(m[1]);f=financials(db,sid);amount=positive(obj.get('amount_cents'))
        if f['collected_cents']+amount>f['sale']['net_total_cents']:raise CError('El cobro excede el saldo neto pendiente')
        date_=day(obj.get('collection_date'));note=str(obj.get('note',''))[:300]
        tx=db.insert('transactions',['txn_date','kind','amount_cents','category','description','project_id','recipient_user_id','reference','status','created_by','created_at'],
         [date_,'income',amount,'Cobro de venta','Cobro neto: '+f['sale']['label'],f['sale']['project_id'],None,'VENTA-'+str(sid),'vigente',uid,now()])
        rid=db.insert('sale_collections',['sale_id','amount_cents','collection_date','transaction_id','note','created_by'],[sid,amount,date_,tx,note,uid])
        db.execute('DELETE FROM {cost_reviews} WHERE sale_id=?',(sid,));audit(db,uid,'COLLECTED','sales',sid,f'{amount} centavos, recibo #{rid}');return rid
    if m:=re.fullmatch(r'/api/collab/sales/(\d+)/(link-income|link-expense)',path):
        sid=int(m[1]);sale=found(db,'sales',sid);txn=found(db,'transactions',obj.get('transaction_id'))
        if txn['status']!='vigente':raise CError('Solo se pueden vincular movimientos aprobados y vigentes')
        if txn['project_id']!=sale['project_id']:raise CError('El movimiento pertenece a otro proyecto')
        if m[2]=='link-income':
            if txn['kind']!='income':raise CError('Se requiere un movimiento de ingreso')
            if db.one('SELECT id FROM {sale_collections} WHERE transaction_id=?',(txn['id'],)):
                raise CError('Este ingreso ya está vinculado a una venta')
            f=financials(db,sid)
            if txn['amount_cents']+f['collected_cents']>sale['net_total_cents']:raise CError('El cobro supera el total pactado')
            rid=db.insert('sale_collections',['sale_id','amount_cents','collection_date','transaction_id','note','created_by'],
                 [sid,txn['amount_cents'],txn['txn_date'],txn['id'],'Vinculado desde Movimientos',uid])
        else:
            if txn['kind']!='expense' or txn['category'] in ('Liquidación colaborador','Remuneración a socio'):
                raise CError('Solo se pueden vincular gastos directos permitidos')
            if db.one('SELECT id FROM {project_costs} WHERE transaction_id=?',(txn['id'],)):
                raise CError('Este gasto ya está asignado a una venta')
            rid=db.insert('project_costs',['project_id','sale_id','category','description','amount_cents','cost_date','status','transaction_id','reference','created_by','created_at'],
                [sale['project_id'],sid,txn['category'],txn['description'],txn['amount_cents'],txn['txn_date'],'pagado',txn['id'],'MOV-'+str(txn['id']),uid,now()])
        db.execute('DELETE FROM {cost_reviews} WHERE sale_id=?',(sid,))
        audit(db,uid,'TRANSACTION_LINKED','sales',sid,f'{m[2]} movimiento {txn["id"]}');return rid
    if path=='/api/collab/assignments':
        sale=found(db,'sales',obj.get('sale_id'));term=found(db,'collab_terms',obj.get('term_id'))
        person=found(db,'collaborators',obj.get('collaborator_id'))
        if term['collaborator_id']!=person['id']:raise CError('El acuerdo no corresponde al colaborador')
        if db.one('SELECT id FROM {assignments} WHERE sale_id=? AND collaborator_id=?',(sale['id'],person['id'])):raise CError('Una sola modalidad por colaborador y venta, sin duplicar comisiones')
        existing=db.one('SELECT COALESCE(SUM(t.rate_bp),0) n FROM {assignments} a JOIN {collab_terms} t ON t.id=a.term_id WHERE a.sale_id=?',(sale['id'],))['n']
        if existing+term['rate_bp']>10000:raise CError('La suma de porcentajes para esta venta excede 100%')
        rid=db.insert('assignments',['sale_id','collaborator_id','term_id','task','evidence','created_by','created_at'],
          [sale['id'],person['id'],term['id'],required(obj.get('task'),'trabajo específico',350),str(obj.get('evidence',''))[:650],uid,now()])
        audit(db,uid,'ASSIGNED','assignments',rid,f'{person["name"]}; venta {sale["id"]}; {term["rate_bp"]/100}%');return rid
    if m:=re.fullmatch(r'/api/collab/assignments/(\d+)/deliver',path):
        rid=int(m[1]);a=found(db,'assignments',rid);ev=required(obj.get('evidence'),'evidencia de trabajo realizado',650)
        db.execute('UPDATE {assignments} SET delivered=1,evidence=? WHERE id=?',(ev,rid))
        audit(db,uid,'WORK_ACCEPTED','assignments',rid,ev);return rid
    if path=='/api/collab/costs':
        sale=found(db,'sales',obj.get('sale_id'));kind=obj.get('status','planeado')
        if kind not in ('planeado','pagado'):raise CError('Estado de costo no permitido')
        val=positive(obj.get('amount_cents'));date_=day(obj.get('cost_date'))
        category=required(obj.get('category'),'categoría',150);description=required(obj.get('description'),'descripción',350)
        tx=None
        if kind=='pagado':
            tx=db.insert('transactions',['txn_date','kind','amount_cents','category','description','project_id','recipient_user_id','reference','status','created_by','created_at'],[date_,'expense',val,category,description,sale['project_id'],None,'COSTO-VENTA-'+str(sale['id']),'pendiente' if val>100000 else 'vigente',uid,now()])
        rid=db.insert('project_costs',['project_id','sale_id','category','description','amount_cents','cost_date','status','transaction_id','reference','created_by','created_at'],[sale['project_id'],sale['id'],category,description,val,date_,kind,tx,str(obj.get('reference',''))[:220],uid,now()])
        db.execute('DELETE FROM {cost_reviews} WHERE sale_id=?',(sale['id'],));audit(db,uid,'COST_REGISTERED','project_costs',rid,f'{kind} {val} centavos');return rid
    if m:=re.fullmatch(r'/api/collab/costs/(\d+)/pay',path):
        rid=int(m[1]);c=found(db,'project_costs',rid)
        if c['status']!='planeado':raise CError('Este costo no está pendiente')
        tx=db.insert('transactions',['txn_date','kind','amount_cents','category','description','project_id','recipient_user_id','reference','status','created_by','created_at'],
         [day(obj.get('payment_date')), 'expense',c['amount_cents'],c['category'],c['description'],c['project_id'],None,'COSTO-'+str(rid),'pendiente' if c['amount_cents']>100000 else 'vigente',uid,now()])
        db.execute('UPDATE {project_costs} SET status=?,transaction_id=? WHERE id=?',('pagado',tx,rid))
        db.execute('DELETE FROM {cost_reviews} WHERE sale_id=?',(c['sale_id'],));audit(db,uid,'COST_PAID','project_costs',rid,str(tx));return rid
    if path=='/api/collab/recurring':
        s=found(db,'sales',obj.get('sale_id'));frequency=obj.get('frequency')
        if frequency not in ('mensual','anual'):raise CError('Periodicidad no válida')
        rid=db.insert('recurring_costs',['project_id','sale_id','category','description','amount_cents','frequency','next_due','active','created_by'],[s['project_id'],s['id'],required(obj.get('category'),'categoría',150),required(obj.get('description'),'concepto',350),positive(obj.get('amount_cents')),frequency,day(obj.get('next_due')),1,uid])
        audit(db,uid,'COST_SCHEDULE_CREATED','recurring_costs',rid,frequency);return rid
    if m:=re.fullmatch(r'/api/collab/recurring/(\d+)/post',path):
        rid=int(m[1]);sched=found(db,'recurring_costs',rid)
        if not sched['active']:raise CError('Costo recurrente inactivo')
        duedate=date.fromisoformat(sched['next_due'])
        if duedate>date.today():raise CError('La obligación todavía no está vencida')
        # Advance preserving a reasonable day-of-month; no duplicate for the due date.
        existing=db.one('SELECT id FROM {project_costs} WHERE recurring_id=? AND cost_date=?',(rid,sched['next_due']))
        if existing:raise CError('Esa obligación ya se generó')
        costid=db.insert('project_costs',['project_id','sale_id','category','description','amount_cents','cost_date','status','recurring_id','reference','created_by','created_at'],[sched['project_id'],sched['sale_id'],sched['category'],sched['description'],sched['amount_cents'],sched['next_due'],'planeado',rid,'RECURRENTE-'+str(rid),uid,now()])
        import calendar
        if sched['frequency']=='mensual':
            ny=duedate.year+(duedate.month//12);nm=(duedate.month%12)+1
        else:ny=duedate.year+1;nm=duedate.month
        new_date=date(ny,nm,min(duedate.day,calendar.monthrange(ny,nm)[1])).isoformat()
        db.execute('UPDATE {recurring_costs} SET next_due=? WHERE id=?',(new_date,rid))
        db.execute('DELETE FROM {cost_reviews} WHERE sale_id=?',(sched['sale_id'],))
        audit(db,uid,'RECURRING_POSTED','project_costs',costid,f'{sched["next_due"]}; siguiente {new_date}');return costid
    if m:=re.fullmatch(r'/api/collab/sales/(\d+)/review',path):
        sid=int(m[1]);f=financials(db,sid)
        if f['unallocated_cents']>0 or f['unpaid_costs'] or f['due_recurring']:
            raise CError('Primero resuelva gastos sin asignar, pendientes y obligaciones recurrentes vencidas')
        db.execute('DELETE FROM {cost_reviews} WHERE sale_id=? AND user_id=?',(sid,uid))
        rid=db.insert('cost_reviews',['sale_id','user_id','fingerprint','created_at'],[sid,uid,f['fingerprint'],now()])
        audit(db,uid,'COSTS_REVIEWED','sales',sid,f['fingerprint'][:16]);return rid
    if m:=re.fullmatch(r'/api/collab/settlements/(\d+)/document',path):
        rid=int(m[1]);v=found(db,'settlements',rid)
        if v['state'] not in ('propuesto','aprobado'):raise CError('No se puede registrar comprobante en un corte ya pagado')
        ref=required(obj.get('document_reference'),'folio del comprobante fiscal',300)
        received=day(obj.get('received_on'))
        due=add_workdays(date.fromisoformat(received),10).isoformat()
        if db.one('SELECT id FROM {settlement_documents} WHERE settlement_id=?',(rid,)):
            db.execute('UPDATE {settlement_documents} SET document_reference=?,received_on=?,due_on=?,created_by=?,created_at=? WHERE settlement_id=?',(ref,received,due,uid,now(),rid))
        else:db.insert('settlement_documents',['settlement_id','document_reference','received_on','due_on','created_by','created_at'],[rid,ref,received,due,uid,now()])
        audit(db,uid,'FISCAL_DOCUMENT_LOGGED','settlements',rid,f'{ref}; fecha límite orientativa {due}');return rid
    if m:=re.fullmatch(r'/api/collab/settlements/(\d+)/cancel',path):
        rid=int(m[1]);v=found(db,'settlements',rid)
        if v['state'] not in ('propuesto','aprobado'):raise CError('Un pago registrado no puede cancelarse por este medio')
        reason=required(obj.get('reason'),'motivo del recálculo',300)
        db.execute("UPDATE {settlements} SET state='cancelado' WHERE id=?",(rid,))
        audit(db,uid,'SETTLEMENT_CANCELLED','settlements',rid,reason);return rid
    if path=='/api/collab/settlements':
        aid=obj.get('assignment_id');a=found(db,'assignments',aid);e=estimate(db,aid)
        if not e['eligible']:raise CError('No se puede liquidar: '+'; '.join(e['blockers']))
        p=period(obj.get('period'));current=date.today().strftime('%Y-%m')
        if p>current:raise CError('No se puede crear una liquidación de un mes futuro')
        old=db.one('SELECT * FROM {settlements} WHERE assignment_id=? AND period=?',(aid,p))
        if old and old['state']!='cancelado':raise CError('Este colaborador ya tiene un corte en ese periodo')
        amount=e['candidate_cents']
        if old:
            rid=old['id']
            db.execute('DELETE FROM {settlement_approvals} WHERE settlement_id=?',(rid,))
            db.execute('DELETE FROM {settlement_documents} WHERE settlement_id=?',(rid,))
            db.execute('UPDATE {settlements} SET base_cents=?,rate_bp=?,amount_cents=?,state=?,created_by=?,created_at=?,created_fingerprint=? WHERE id=?',(e['base_cents'],e['rate_bp'],amount,'propuesto',uid,now(),e['fingerprint'],rid))
        else:rid=db.insert('settlements',['assignment_id','period','base_cents','rate_bp','amount_cents','state','created_by','created_at','created_fingerprint'],[aid,p,e['base_cents'],e['rate_bp'],amount,'propuesto',uid,now(),e['fingerprint']])
        audit(db,uid,'SETTLEMENT_CREATED','settlements',rid,f'{amount} centavos; contrato {a["term_id"]}');return rid
    if m:=re.fullmatch(r'/api/collab/settlements/(\d+)/(approve|pay)',path):
        rid=int(m[1]);operation=m[2];v=found(db,'settlements',rid)
        a=found(db,'assignments',v['assignment_id']);e=estimate(db,a['id'])
        f=financials(db,a['sale_id']);t=found(db,'collab_terms',a['term_id']);sale=f['sale']
        if operation=='approve':
            if v['state'] not in ('propuesto','aprobado'):raise CError('Corte no aprobable')
            if f['fingerprint']!=v['created_fingerprint'] or f['review_votes']<2:raise CError('La base/costos cambiaron o falta revisión dual. Anule el borrador y recalcule (no se admiten aprobaciones obsoletas).')
            if not t['active']:raise CError('Contrato no validado')
            if not db.one('SELECT id FROM {settlement_approvals} WHERE settlement_id=? AND user_id=?',(rid,uid)):
                db.insert('settlement_approvals',['settlement_id','user_id','created_at'],[rid,uid,now()])
            n=db.one('SELECT COUNT(*) n FROM {settlement_approvals} WHERE settlement_id=?',(rid,))['n']
            if n>=2:db.execute('UPDATE {settlements} SET state=? WHERE id=?',('aprobado',rid))
            audit(db,uid,'SETTLEMENT_APPROVED','settlements',rid,f'{n} votos');return rid
        if v['state']!='aprobado':raise CError('Se requieren dos autorizaciones')
        if f['fingerprint']!=v['created_fingerprint'] or f['review_votes']<2:raise CError('El estado financiero cambió desde el corte; debe revisarse antes de pagar')
        if not t['active']:raise CError('Contrato sin validar')
        if t['trigger_kind']=='mariano_full' and f['collected_cents']<sale['net_total_cents']:raise CError('Falta liquidar el total de la venta POS')
        if not a['delivered']:raise CError('No hay evidencia aceptada del trabajo')
        if f['due_recurring'] or f['unpaid_costs'] or f['unallocated_cents']:raise CError('Hay gastos pendientes de conciliación')
        ref=required(obj.get('payment_reference'),'folio de transferencia ejecutada',300)
        if t['trigger_kind']=='enrique_monthly':
            fiscal=db.one('SELECT * FROM {settlement_documents} WHERE settlement_id=?',(rid,))
            if not fiscal:raise CError('Falta registrar la fecha de recepción del CFDI/recibo del colaborador')
        # Limit payouts by actual receipts, costs and previous PAID commissions; proposed un-paid not double count.
        paid=db.one("SELECT COALESCE(SUM(amount_cents),0) n FROM {settlements} WHERE assignment_id=? AND state='pagado'",(a['id'],))['n']
        cap=(f['available_base_cents']*t['rate_bp'])//10000
        if paid+v['amount_cents']>cap:raise CError('El monto supera la ganancia todavía disponible')
        updated=db.execute("UPDATE {settlements} SET state='pagado',paid_at=?,voucher_reference=? WHERE id=? AND state='aprobado'",(now(),ref,rid))
        if updated.rowcount!=1:raise CError('Corte ya procesado')
        tx=db.insert('transactions',['txn_date','kind','amount_cents','category','description','project_id','recipient_user_id','reference','status','created_by','created_at'],[date.today().isoformat(),'expense',v['amount_cents'],'Liquidación colaborador','Pago '+t['title']+' — '+str(a['id']),sale['project_id'],None,'LIQ-'+str(rid)+' '+ref,'vigente',uid,now()])
        db.execute('UPDATE {settlements} SET paid_transaction_id=? WHERE id=?',(tx,rid))
        audit(db,uid,'SETTLEMENT_PAID','settlements',rid,f'folio {ref}; {v["amount_cents"]} centavos');return rid
    raise CError('Ruta de colaboración no encontrada')
