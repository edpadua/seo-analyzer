from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from engine import get_advanced_audit

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/analyze", response_class=HTMLResponse)
async def handle_analysis(request: Request, url: str = Form(...), keyword: str = Form(...)):
    if not url.startswith('http'):
        url = 'https://' + url
    
    report_text = get_advanced_audit(url, keyword)
    
    return templates.TemplateResponse("report.html", {
        "request": request, 
        "report_text": report_text
    })