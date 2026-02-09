import os
import json
import requests
from bs4 import BeautifulSoup
from fastapi import Body 
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv

# Importações locais
import models
from database import engine, get_db, SessionLocal
from engine import get_advanced_audit, get_ai_seo_insights, get_competitor_battle, extract_main_keyword

# Configuração inicial
load_dotenv()
models.Base.metadata.create_all(bind=engine)

import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

app = FastAPI()

oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# Middleware para verificar status de ranking
@app.middleware("http")
async def add_rank_status_to_context(request: Request, call_next):
    user_session = request.session.get('user')
    request.state.rank_up = False
    if user_session:
        db = SessionLocal()
        user = db.query(models.User).filter(models.User.email == user_session['email']).first()
        if user:
            last_two = db.query(models.KeywordTracking).filter(
                models.KeywordTracking.user_id == user.id
            ).order_by(models.KeywordTracking.created_at.desc()).limit(2).all()
            if len(last_two) >= 2:
                atual, anterior = last_two[0].position, last_two[1].position
                if (anterior == 0 and atual > 0) or (0 < atual < anterior):
                    request.state.rank_up = True
        db.close()
    return await call_next(request)

app.add_middleware(
    SessionMiddleware, 
    secret_key=os.getenv("SECRET_KEY", "chave-secreta-provisoria"),
    same_site="lax",  # Permite que o cookie sobreviva ao redirecionamento do Google
    https_only=False   # Mantenha False se não tiver domínio próprio com SSL forçado
)


app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- ROTAS DE AUTENTICAÇÃO ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user = request.session.get('user')
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.post("/auth/login")
async def auth_login(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        user = models.User(email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
    request.session['user'] = {"email": user.email, "id": user.id, "name": email.split('@')[0]}
    return RedirectResponse(url='/dashboard', status_code=303)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url='/')

@app.get("/login")
async def login_page_google(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


# Rota para MOSTRAR a página (GET)
@app.get("/login-email", response_class=HTMLResponse)
async def login_email_page(request: Request):
    return templates.TemplateResponse("login-email.html", {"request": request})

# Rota para PROCESSAR o login (POST) - Adicione esta exatamente assim:
@app.post("/login-email")
async def auth_login_direct(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        user = models.User(email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
    
    request.session['user'] = {
        "email": user.email, 
        "id": user.id, 
        "name": email.split('@')[0]
    }
    # O status_code 303 é OBRIGATÓRIO aqui para o Koyeb
    return RedirectResponse(url='/dashboard', status_code=303)

"""@app.get("/login-email", response_class=HTMLResponse)
async def login_email_page(request: Request):
    return templates.TemplateResponse("login-email.html", {"request": request})"""

@app.get("/login/google")
async def login_google(request: Request):
    # Gera a URL de redirecionamento para o Google
    redirect_uri = request.url_for('auth_callback')
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth", name="auth_callback")
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    # Recebe o token do Google
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get('userinfo')
    
    if user_info:
        email = user_info['email']
        # Verifica ou cria o usuário no banco
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            user = models.User(email=email, name=user_info.get('name'))
            db.add(user)
            db.commit()
            db.refresh(user)
            
        # Salva na sessão
        request.session['user'] = {
            "email": user.email, 
            "id": user.id, 
            "name": user_info.get('name', email.split('@')[0])
        }
        
    return RedirectResponse(url='/dashboard')

# --- DASHBOARD E ADMIN ---

@app.get("/dashboard")
async def dashboard(request: Request, db: Session = Depends(get_db)):
    user_session = request.session.get('user')
    if not user_session: return RedirectResponse(url='/login-email', status_code=303)
    db_user = db.query(models.User).filter(models.User.email == user_session['email']).first()
    
    history_chart = db.query(models.KeywordTracking).filter(models.KeywordTracking.user_id == db_user.id).order_by(models.KeywordTracking.created_at.asc()).limit(20).all()
    last_two = db.query(models.KeywordTracking).filter(models.KeywordTracking.user_id == db_user.id).order_by(models.KeywordTracking.created_at.desc()).limit(2).all()
    
    labels = [h.created_at.strftime("%d/%m") for h in history_chart]
    values = [h.position for h in history_chart]
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, "user": db_user, "labels": json.dumps(labels), "values": json.dumps(values), "history": last_two
    })

# Rota Admin Corrigida
@app.get("/admin")
async def admin_panel(request: Request, db: Session = Depends(get_db)):
    user_session = request.session.get('user')
    if not user_session:
        return RedirectResponse(url='/login-email', status_code=303)

    
    db_user = db.query(models.User).filter(models.User.email == user_session['email']).first()
    if not db_user:
        return RedirectResponse(url='/login-email')

    audits = db.query(models.AuditHistory).filter(models.AuditHistory.user_id == db_user.id).order_by(models.AuditHistory.created_at.desc()).all()
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "user": user_session,
        "user_db": db_user,
        "history": audits  # Alterado de 'audits' para 'history' para bater com o HTML
    })

# --- MOTOR DE AUDITORIA ---

@app.post("/audit")
async def handle_audit(request: Request, url: str = Form(...), keyword_mode: str = Form(...), keyword: str = Form(None), db: Session = Depends(get_db)):
    user_session = request.session.get('user')
    if not user_session: 
        return RedirectResponse(url='/login-email', status_code=303)
    
    db_user = db.query(models.User).filter(models.User.email == user_session['email']).first()

    # 1. Determinar a palavra-chave final
    final_keyword = keyword if keyword_mode == "manual" else extract_main_keyword(url)
    if not final_keyword: 
        final_keyword = "SEO Analysis"

    # 2. Executar a auditoria técnica (Restaurado o sec_mob)
    try:
        # Importante: Garantir que a desestruturação combine com o retorno da sua engine.py
        report_html, scores, word_counts, vitals, sec_mob = get_advanced_audit(
            url, 
            final_keyword, 
            db_user.pagespeed_api_key,
            db_user.openpagerank_api_key
        )
    except Exception as e:
        print(f"Erro na auditoria: {e}")
        report_html = f"<div class='alert alert-danger'>Erro técnico: {str(e)}</div>"
        scores = {"performance": 0, "on_page": 0, "semantic": 0, "authority": 0, "schema": 0}
        vitals = {"lcp": {"value": "N/A", "status": "gray"}, "fcp": {"value": "N/A", "status": "gray"}, "cls": {"value": "N/A", "status": "gray"}}
        sec_mob = {} # Dicionário vazio para não quebrar o template

    # 3. Insights da IA
    ai_insights = None
    if db_user.ai_api_key:
        try:
            # Pegamos uma amostra do conteúdo para a IA processar
            res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            words = soup.get_text().split()
            ai_insights = get_ai_seo_insights(
                final_keyword, 
                " ".join(words[:300]), 
                db_user.ai_provider, 
                db_user.ai_api_key, 
                db_user.ai_model
            )
        except:
            ai_insights = None

    # 4. Salvar no Banco de Dados
    new_audit = models.AuditHistory(
        user_id=db_user.id, 
        url=url, 
        keyword=final_keyword,
        score_performance=scores.get('performance', 0), 
        score_on_page=scores.get('on_page', 0),
        score_semantic=scores.get('semantic', 0), 
        score_authority=scores.get('authority', 0),
        score_schema=scores.get('schema', 0), 
        report_html=report_html,
        ai_insights_json=json.dumps(ai_insights) if ai_insights else None
    )
    db.add(new_audit)
    db.commit()

    # 5. Renderizar Resposta (Enviando sec_mob para o HTML)
    return templates.TemplateResponse("report.html", {
        "request": request, 
        "report_html": report_html, 
        "scores": scores, 
        "vitals": vitals,
        "sec_mob": sec_mob,  # <--- CRUCIAL: Reintegrado aqui
        "scores_json": json.dumps(scores), 
        "ai_insights": ai_insights, 
        "keyword": final_keyword, 
        "url": url
    })

@app.post("/battle")
async def handle_battle(request: Request, url1: str = Form(...), url2: str = Form(...), keyword_mode: str = Form(...), keyword: str = Form(None), db: Session = Depends(get_db)):
    user_session = request.session.get('user')
    if not user_session: return RedirectResponse(url='/login-email', status_code=303)
    db_user = db.query(models.User).filter(models.User.email == user_session['email']).first()

    # Define a palavra-chave
    final_keyword = keyword if keyword_mode == "manual" else extract_main_keyword(url1)
    if not final_keyword: final_keyword = "SEO Analysis"
    
    ps_key = db_user.pagespeed_api_key or os.getenv("PAGESPEED_API_KEY")
    serp_key = db_user.serpapi_key or os.getenv("SERPAPI_KEY")
    opr_key = db_user.openpagerank_api_key or os.getenv("OPENPAGERANK_API_KEY")

    try:
        # A ordem das 9 variáveis deve ser EXATAMENTE a do engine.py
        h1, s1, w1, h2, s2, w2, gap_html, v1, v2 = get_competitor_battle(url1, url2, final_keyword, serp_key, ps_key, opr_key)

        # SALVAR NO HISTÓRICO
        new_audit = models.AuditHistory(
            user_id=db_user.id, 
            url=url1, 
            keyword=final_keyword,
            score_performance=s1.get('performance', 0), 
            score_on_page=s1.get('on_page', 0),
            score_semantic=s1.get('semantic', 0), 
            score_authority=s1.get('authority', 0),
            score_schema=s1.get('schema', 0), 
            report_html=h1
        )
        db.add(new_audit)
        db.commit()

        print(f"DEBUG - Vitals Site 1: {v1}")
        print(f"DEBUG - Vitals Site 2: {v2}")
        # RETORNO ÚNICO PARA O TEMPLATE
        return templates.TemplateResponse("comparison.html", {
            "request": request,
            "u1": url1, 
            "u2": url2, 
            "keyword": final_keyword,
            "h1": h1, 
            "h2": h2,
            "s1_json": json.dumps(s1), 
            "s2_json": json.dumps(s2),
            "gap_html": gap_html, # Usando o nome correto que vem do engine
            "v1": v1, 
            "v2": v2, 
            "user": db_user
        })
        
    except Exception as e:
        print(f"Erro detalhado no battle: {e}")
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "error": f"Erro no duelo: {str(e)}", 
            "user": db_user
        })

@app.get("/report/{audit_id}")
async def view_report(audit_id: int, request: Request, db: Session = Depends(get_db)):
    user_session = request.session.get('user')
    if not user_session: return RedirectResponse(url='/login-email', status_code=303)
    audit = db.query(models.AuditHistory).filter(models.AuditHistory.id == audit_id).first()
    if not audit: return RedirectResponse(url='/admin')

    scores = {
        "performance": audit.score_performance,
        "on_page": audit.score_on_page,
        "semantic": audit.score_semantic,
        "authority": audit.score_authority,
        "schema": audit.score_schema
    }

    # Recupera os insights salvos como JSON
    ai_insights = json.loads(audit.ai_insights_json) if audit.ai_insights_json else None

    return templates.TemplateResponse("report.html", {
        "request": request,
        "url": audit.url,           # Corrigido: audit.url
        "keyword": audit.keyword,   # Corrigido: audit.keyword
        "scores_json": json.dumps(scores),
        "vitals": {},               # Vitals não são salvos no banco por padrão nesta estrutura
        "sec_mob": {}, 
        "ai_insights": ai_insights,
        "report_html": audit.report_html # Corrigido: audit.report_html
    })

@app.get("/delete/{audit_id}")
async def delete_audit(audit_id: int, request: Request, db: Session = Depends(get_db)):
    user_session = request.session.get('user')
    if not user_session: return RedirectResponse(url='/login-email', status_code=303)
    
    audit = db.query(models.AuditHistory).filter(models.AuditHistory.id == audit_id).first()
    if audit:
        db.delete(audit)
        db.commit()
    return RedirectResponse(url='/admin')

# 2. NOVA ROTA: Exclusão em Massa (Multiple)
@app.post("/delete-multiple")
async def delete_multiple(request: Request, db: Session = Depends(get_db)):
    user_session = request.session.get('user')
    if not user_session: return RedirectResponse(url='/login-email')
    
    # Pegamos os dados do formulário
    form_data = await request.form()
    audit_ids = form_data.getlist("audit_ids") # Pega todos os IDs marcados
    
    if audit_ids:
        # Deleta apenas os que pertencem ao usuário por segurança
        db_user = db.query(models.User).filter(models.User.email == user_session['email']).first()
        db.query(models.AuditHistory).filter(
            models.AuditHistory.id.in_(audit_ids),
            models.AuditHistory.user_id == db_user.id
        ).delete(synchronize_session=False)
        db.commit()
        
    return RedirectResponse(url='/admin', status_code=303)

@app.post("/update-settings")
async def update_settings(request: Request, db: Session = Depends(get_db), pagespeed_api_key: str = Form(None), openpagerank_api_key: str = Form(None), serpapi_key: str = Form(None), ai_provider: str = Form(None), ai_api_key: str = Form(None), ai_model: str = Form(None)):
    user_session = request.session.get('user')
    db_user = db.query(models.User).filter(models.User.email == user_session['email']).first()
    if db_user:
        db_user.pagespeed_api_key = pagespeed_api_key
        db_user.openpagerank_api_key = openpagerank_api_key
        db_user.serpapi_key = serpapi_key
        db_user.ai_provider = ai_provider
        db_user.ai_api_key = ai_api_key
        db_user.ai_model = ai_model
        db.commit()
    return RedirectResponse(url='/admin', status_code=303)

"""if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)"""

if __name__ == "__main__":
    import uvicorn
    import os
    # O Koyeb define automaticamente a variável de ambiente 'PORT'
    port = int(os.environ.get("PORT", 8000))
    # O host DEVE ser 0.0.0.0 para aceitar conexões externas
    uvicorn.run("main:app", host="0.0.0.0", port=port)