import requests
from bs4 import BeautifulSoup
import re
import unicodedata
import json
import os
from urllib.parse import urlparse
from collections import Counter
from sqlalchemy.orm import Session
from urllib.parse import urlparse
# Se você for usar o modelo KeywordTracking aqui dentro, garanta que ele também esteja importado
import models

# --- UTILITÁRIOS E NORMALIZAÇÃO ---

def extract_main_keyword(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Tentar Meta Keywords
        meta_k = soup.find("meta", attrs={"name": "keywords"})
        if meta_k and meta_k.get("content"):
            return meta_k.get("content").split(',')[0].strip()
        
        # 2. Tentar H1
        h1 = soup.find("h1")
        if h1:
            return h1.get_text().strip()

        # 3. EXTRAÇÃO POR DENSIDADE (Se as tags falharem)
        # Pegamos apenas o texto dentro do <body>, ignorando scripts e estilos
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()
            
        text = soup.get_text().lower()
        # Regex para pegar apenas palavras com mais de 3 letras (evita "de", "com", etc)
        words = re.findall(r'\b\w{4,}\b', text)
        
        # Lista de "stopwords" (palavras a ignorar)
        stopwords = ['sobre', 'mais', 'para', 'como', 'fazer', 'página', 'todos', 'direitos']
        filtered_words = [w for w in words if w not in stopwords]
        
        if filtered_words:
            # Conta a frequência e pega a palavra mais comum
            most_common = Counter(filtered_words).most_common(1)
            return most_common[0][0].capitalize()

        return "SEO Analysis"
    except:
        return "SEO Analysis"

def normalize_text(text):
    """Normaliza texto removendo acentos e caracteres especiais."""
    if not text: return ""
    text = text.lower().replace("-", " ").replace("_", " ")
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
    return " ".join(text.split())

def get_semantic_analysis(text):
    """Analisa a riqueza vocabular e retorna um score de 0 a 100."""
    stops = set(['este', 'esta', 'esse', 'essa', 'isso', 'para', 'com', 'mais', 'muito', 'pelo', 'pela', 'seus', 'suas', 'como', 'sobre', 'tudo', 'todos', 'onde', 'quando', 'quem'])
    words = re.findall(r'\b\w{4,}\b', text.lower())
    filtered = [w for w in words if w not in stops]
    common = Counter(filtered).most_common(8)
    
    unique_ratio = len(set(words)) / len(words) if words else 0
    
    # Ajuste de escala para o Gráfico (0 a 100)
    if unique_ratio > 0.5:
        richness = "Alta"
        richness_score = 100
    elif unique_ratio > 0.3:
        richness = "Média"
        richness_score = 70
    else:
        richness = "Baixa"
        richness_score = 40
        
    return common, richness, richness_score, filtered

# --- MÉTRICAS EXTERNAS (APIs) ---

def get_authority_metrics(url, opr_key):
    """Obtém métricas de autoridade via Open Page Rank."""
    domain = urlparse(url).netloc
    api_url = f"https://openpagerank.com/api/v1.0/getPageRank?domains[]={domain}"
    try:
        headers = {'API-OPR': opr_key}
        response = requests.get(api_url, headers=headers, timeout=10).json()
        if response.get('status_code') == 200:
            data = response['response'][0]
            rp = data.get('page_rank_decimal', 0)
            rank = data.get('rank_int', "N/A")
            da = int(float(rp) * 10)
            return {
                "pr": f"{rp}/10", 
                "gr": f"#{rank}", 
                "da": da, 
                "status": "Forte" if da > 30 else "Iniciante"
            }
    except: pass
    return {"pr": "1.0/10", "gr": "#N/A", "da": 10, "status": "Iniciante"}

def get_pagespeed_metrics(url, api_key):
    try:
        # Usando a API v5 para garantir dados do Lighthouse
        api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&key={api_key}&category=performance"
        r = requests.get(api_url, timeout=60)
        data = r.json()
        audits = data.get('lighthouseResult', {}).get('audits', {})
        
        def get_v(name):
            audit = audits.get(name, {})
            score = audit.get('score', 0)
            status = "success" if score >= 0.9 else "warning" if score >= 0.5 else "danger"
            return audit.get('displayValue', 'N/A'), status

        lcp_val, lcp_stat = get_v('largest-contentful-paint')
        fcp_val, fcp_stat = get_v('first-contentful-paint')
        cls_val, cls_stat = get_v('cumulative-layout-shift')

        return {
            'score': data.get('lighthouseResult', {}).get('categories', {}).get('performance', {}).get('score', 0) * 100,
            'lcp_val': lcp_val, 'lcp_status': lcp_stat,
            'fcp_val': fcp_val, 'fcp_status': fcp_stat,
            'cls_val': cls_val, 'cls_status': cls_stat
        }
    except:
        return None

def get_keyword_gap(url1, url2, keyword, api_key):
    """Busca dados de ranking na SerpApi e compara os dois domínios."""
    import requests
    
    params = {
        "engine": "google",
        "q": keyword,
        "api_key": api_key
    }
    
    try:
        response = requests.get("https://serpapi.com/search", params=params, timeout=15)
        data = response.json()
        results = data.get("organic_results", [])
        
        # Lógica para encontrar a posição dos dois sites
        pos1, pos2 = "N/A", "N/A"
        domain1 = urlparse(url1).netloc.replace("www.", "")
        domain2 = urlparse(url2).netloc.replace("www.", "")

        for idx, res in enumerate(results):
            link = res.get("link", "")
            if domain1 in link: pos1 = idx + 1
            if domain2 in link: pos2 = idx + 1

        # Retorna o HTML formatado para o relatório
        return f"""
        <div class='audit-card'>
            <div class='card-header'>Rank Tracker - Disputa Direta</div>
            <div class='card-body'>
                <p>Posição de {domain1}: <strong>{pos1}º lugar</strong></p>
                <p>Posição de {domain2}: <strong>{pos2}º lugar</strong></p>
            </div>
        </div>
        """
    except Exception as e:
        return f"<p>Erro ao processar SerpApi: {e}</p>"

def update_rank_history(db: Session, user_id: int, url: str, keyword: str, serp_key: str):
    """
    Consulta a posição real da URL no Google e guarda no histórico do banco de dados.
    """
    import requests
    from models import KeywordTracking # Import local para evitar importação circular
    from urllib.parse import urlparse
    
    # Extrai apenas o domínio para comparação (ex: 'site.com.br')
    domain = urlparse(url).netloc.replace("www.", "")
    
    params = {
        "q": keyword,
        "location": "Brazil",
        "hl": "pt",
        "gl": "br",
        "google_domain": "google.com.br",
        "api_key": serp_key,
        "num": 100  
    }

    try:
        response = requests.get("https://serpapi.com/search", params=params, timeout=30)
        data = response.json()
        results = data.get("organic_results", [])

        current_pos = 0 # Assume 0 se não estiver no Top 100
        
        for res in results:
            # Verifica se o nosso domínio está contido na URL do resultado
            if domain in res.get("link", ""):
                current_pos = res.get("position")
                break
        
        # Cria o registro no histórico
        new_rank = KeywordTracking(
            user_id=user_id,
            url=url,
            keyword=keyword,
            position=current_pos
        )
        
        db.add(new_rank)
        db.commit()
        
        return current_pos
    except Exception as e:
        print(f"Erro ao atualizar ranking: {e}")
        return None

# --- INTELIGÊNCIA ARTIFICIAL ---

def get_ai_seo_insights(keyword, content_snippet, provider, api_key, model):
    if not api_key or not provider: 
        return None
    
    provider = provider.lower()
    prompt = f"""
    Analise a palavra-chave "{keyword}" e este resumo: "{content_snippet[:1000]}".
    Retorne APENAS um JSON estrito (sem markdown, sem explicações) com esta estrutura:
    {{
      "suggested_title": "Título SEO",
      "suggested_meta": "Meta descrição",
      "content_analysis": "Análise estratégica"
    }}
    """

    try:
        if 'gemini' in provider:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model_ai = genai.GenerativeModel(model or "gemini-1.5-flash")
            response = model_ai.generate_content(prompt)
            # Limpeza de possíveis marcações de Markdown que quebram o JSON
            txt = response.text.replace('```json', '').replace('```', '').strip()
            return json.loads(txt)
            
        elif 'openai' in provider:
            import openai
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model or "gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            txt = response.choices[0].message.content.replace('```json', '').replace('```', '').strip()
            return json.loads(txt)
    except Exception as e:
        print(f"--- ERRO NA IA ---: {e}") # Verifique o seu terminal/console!
        return None

def get_pagespeed_metrics(url, api_key):
    """Extrai métricas detalhadas do Core Web Vitals via PageSpeed v5."""
    try:
        api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&key={api_key}&category=performance"
        r = requests.get(api_url, timeout=60)
        data = r.json()
        
        audits = data.get('lighthouseResult', {}).get('audits', {})
        
        def parse_v(name):
            audit = audits.get(name, {})
            val = audit.get('displayValue', 'N/A')
            score = audit.get('score', 0)
            # Define o status para o CSS do Bootstrap
            if score >= 0.9: status = "success"  # Verde
            elif score >= 0.5: status = "warning" # Amarelo
            else: status = "danger"              # Vermelho
            return {"value": val, "status": status}

        return {
            "score": data.get('lighthouseResult', {}).get('categories', {}).get('performance', {}).get('score', 0) * 100,
            "lcp": parse_v('largest-contentful-paint'),
            "fcp": parse_v('first-contentful-paint'),
            "cls": parse_v('cumulative-layout-shift')
        }
    except Exception as e:
        print(f"Erro PageSpeed detalhado: {e}")
        return None

def extract_semantic_terms(text, limit=15):
    """Extrai termos relevantes ignorando stop words comuns."""
    # Lista estendida de stop words em português
    stop_words = {'com', 'para', 'uma', 'sobre', 'mais', 'muito', 'pelo', 'pela', 'seus', 'suas', 'como', 'onde', 'qual'}
    
    # Limpeza e tokenização simples
    words = re.findall(r'\b[a-z]{4,15}\b', text.lower())
    filtered_words = [w for w in words if w not in stop_words]
    
    # Retorna os termos mais frequentes que representam o "tópico" do conteúdo
    return [term for term, count in Counter(filtered_words).most_common(limit)]


def get_ai_content_strategy(url1, text1, url2, text2, keyword, ai_client, model):
    """Gera o Gap de Tópicos, Meta Tags e agora as palavras LSI."""
    terms1 = extract_semantic_terms(text1)
    terms2 = extract_semantic_terms(text2)
    
    prompt = f"""
    Analise o SEO de conteúdo para a palavra-chave: "{keyword}"
    Meu Site ({url1}): {", ".join(terms1)}
    Concorrente ({url2}): {", ".join(terms2)}
    
    Responda em JSON estrito:
    {{
        "topic_gap": "lista de 3 termos que o concorrente usa e eu não",
        "lsi_keywords": ["termo1", "termo2", "termo3", "termo4", "termo5"], 
        "meta_suggestions": [
            {{"title": "Sugestão 1", "desc": "Meta desc 1"}},
            {{"title": "Sugestão 2", "desc": "Meta desc 2"}},
            {{"title": "Sugestão 3", "desc": "Meta desc 3"}}
        ],
        "content_advice": "Dica estratégica rápida"
    }}
    """
    
    try:
        response = ai_client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": "Você é um especialista em SEO NLP."},
                      {"role": "user", "content": prompt}],
            response_format={ "type": "json_object" }
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"error": str(e)}

# --- AUDITORIA TÉCNICA PRINCIPAL ---

# No engine.py

def check_security_and_mobile(url):
    """Verifica se o site é seguro (HTTPS) e possui configurações básicas para mobile."""
    results = {
        "has_ssl": url.startswith("https"),
        "has_viewport": False,
        "is_compressed": False,
        "security_score": 0
    }
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Verificação de Mobile-Friendly (Viewport)
        # Sem essa tag, o site não renderiza corretamente em celulares
        viewport = soup.find("meta", attrs={"name": "viewport"})
        if viewport:
            results["has_viewport"] = True
            
        # 2. Verificação de Performance/Compressão (Gzip ou Brotli)
        content_encoding = response.headers.get("Content-Encoding", "").lower()
        if "gzip" in content_encoding or "br" in content_encoding:
            results["is_compressed"] = True

        # 3. Cálculo Simples de Pontuação de Segurança/Mobile
        score = 0
        if results["has_ssl"]: score += 40
        if results["has_viewport"]: score += 40
        if results["is_compressed"]: score += 20
        results["security_score"] = score

    except Exception as e:
        print(f"Erro na verificação de segurança/mobile: {e}")
        
    return results

def check_security_and_mobile(url):
    results = {
        "has_ssl": url.startswith("https"),
        "has_viewport": False,
        "is_compressed": False
    }
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Verifica se tem tag mobile
        results["has_viewport"] = bool(soup.find("meta", attrs={"name": "viewport"}))
        
        # Verifica compressão Gzip/Brotli
        encoding = response.headers.get("Content-Encoding", "").lower()
        results["is_compressed"] = any(x in encoding for x in ["gzip", "br", "deflate"])
    except:
        pass
    return results


def detect_cms(soup, html_text, headers):
    """Detecta a plataforma/CMS com heurísticas avançadas."""
    html_low = html_text.lower()
    
    # 1. Verificação via Meta Tag Generator
    gen = soup.find("meta", attrs={"name": "generator"})
    gen_content = gen.get("content", "").lower() if gen else ""
    
    # --- DICIONÁRIO DE ASSINATURAS ---
    if "wordpress" in gen_content or "/wp-content/" in html_low:
        if "woocommerce" in html_low: return "WordPress + WooCommerce"
        return "WordPress"
    
    if "shopify" in html_low or "cdn.shopify.com" in html_low:
        return "Shopify"
    
    if "vtex" in html_low or "vtex-scripts" in html_low:
        return "VTEX"
    
    if "nuvemshop" in html_low or "tiendanube" in html_low:
        return "Nuvemshop"
        
    if "tray.com.br" in html_low or "tray-cdn" in html_low:
        return "Tray"

    if "rdstation" in html_low or "static.rdstation.com.br" in html_low:
        return "RD Station (Landing Page)"

    if "wix.com" in html_low or "wix-static" in html_low:
        return "Wix"

    if "webflow" in html_low or "data-wf-page" in html_low:
        return "Webflow"

    if "hubspot" in html_low or "hs-scripts" in html_low:
        return "HubSpot"

    # --- FRAMEWORKS MODERNOS ---
    if "_next/static" in html_low: return "Next.js"
    if "gatsby-static" in html_low: return "Gatsby"
    if "react" in html_low and "data-reactroot" in html_low: return "React.js Custom"
    
    # --- OUTROS ---
    if "magento" in html_low or "mage/" in html_low: return "Magento"
    if "joomla" in gen_content: return "Joomla"
    if "drupal" in gen_content: return "Drupal"
    
    return "Customizada / Não Identificada"

def get_advanced_audit(url, keyword, ps_key=None, opr_key=None):
    """
    Executa a auditoria SEO completa com Core Web Vitals, Checklist On-page, 
    Análise Semântica, Segurança e Otimização Mobile.
    Retorna: (report_html, numeric_scores, words_list, vitals_data, sec_mob)
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # Inicialização de variáveis
    numeric_scores = {"performance": 0, "on_page": 0, "semantic": 0, "authority": 0, "schema": 0}
    vitals_data = {
        "lcp": {"value": "N/A", "status": "gray"},
        "fcp": {"value": "N/A", "status": "gray"},
        "cls": {"value": "N/A", "status": "gray"}
    }
    words_list = []
    sec_mob = {"security_score": 0, "mobile_score": 0, "details": {"sec": [], "mob": []}}
    report_html = ""

    def r_row(label, val, status=False):
        if status:
            # Lista de termos que ativam a cor verde (tag-sim)
            positivos = ["Sim", "✅", "Forte", "Alta", "Correta", "Ativa", "WordPress", 
                         "Shopify", "VTEX", "Nuvemshop", "Tray", "RD Station", "Wix", 
                         "Webflow", "HubSpot", "Next.js", "Gatsby", "Magento"]
            
            is_ok = any(x.lower() in str(val).lower() for x in positivos)
            cl = "tag-sim" if is_ok else "tag-nao"
            return f'<div class="data-row"><span class="label">{label}:</span><span class="tag {cl}">{val}</span></div>'
        return f'<div class="data-row"><span class="label">{label}:</span><span class="value">{val}</span></div>'
    try:
        # 1. ACESSO AO SITE E EXTRAÇÃO
        res = requests.get(url, headers=headers, timeout=30)
        res.encoding = res.apparent_encoding 
        soup = BeautifulSoup(res.text, 'html.parser')

        # 1. ACESSO E DETECÇÃO DE PLATAFORMA
        
        platform = detect_cms(soup, res.text, res.headers)
        
        # Limpeza para contagem de palavras e semântica
        soup_c = BeautifulSoup(res.text, 'html.parser')
        for s in soup_c(["script", "style", "nav", "footer", "header", "aside", "form"]): 
            s.decompose()
        
        full_text = soup_c.get_text()
        words_list = re.findall(r'\w+', full_text.lower())
        word_count = len(words_list)
        
        kw_norm = normalize_text(keyword)
        
        # 2. COLETA DE METADADOS
        title_tag = soup.title.string.strip() if soup.title else ""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        meta_content = meta_desc['content'] if meta_desc and meta_desc.has_attr('content') else ""
        meta_txt_norm = normalize_text(meta_content)
        
        # 3. VERIFICAÇÕES TÉCNICAS (BASE PARA O CHECKLIST)
        is_https = url.startswith("https")
        has_favicon = soup.find("link", rel=re.compile(r"icon", re.I)) is not None
        encoding_header = res.headers.get('Content-Encoding', '').lower()
        has_compression = any(c in encoding_header for c in ['gzip', 'br', 'deflate', 'zstd'])
        
        robots = soup.find("meta", attrs={"name": "robots"})
        is_indexable = "noindex" not in (robots["content"].lower() if robots and robots.has_attr("content") else "")
        has_canonical = soup.find("link", rel="canonical") is not None
        has_social = soup.find("meta", property=re.compile(r"^og:")) is not None

        # 4. ANÁLISE ESPECÍFICA: SEGURANÇA E MOBILE (Dicionário sec_mob)
        h = res.headers
        sec_items = [
            (is_https, "Protocolo HTTPS"),
            ("Strict-Transport-Security" in h, "HSTS Ativo"),
            ("X-Frame-Options" in h, "Proteção Clickjacking"),
            ("X-Content-Type-Options" in h, "Proteção MIME Sniffing")
        ]
        
        viewport = soup.find("meta", attrs={"name": "viewport"})
        mob_items = [
            (viewport is not None, "Meta Viewport Definida"),
            ("width=device-width" in (viewport["content"] if viewport else ""), "Ajuste Device-Width"),
            ("@media" in res.text, "Media Queries Detectadas"),
            (len(soup.find_all("picture")) > 0 or "srcset" in res.text, "Imagens Responsivas")
        ]

        sec_mob["security_score"] = (sum(1 for ok, _ in sec_items if ok) / len(sec_items)) * 100
        sec_mob["mobile_score"] = (sum(1 for ok, _ in mob_items if ok) / len(mob_items)) * 100
        sec_mob["details"]["sec"] = [{"label": l, "status": "Sim" if ok else "Não"} for ok, l in sec_items]
        sec_mob["details"]["mob"] = [{"label": l, "status": "Sim" if ok else "Não"} for ok, l in mob_items]

        # 5. LISTA DE CRITÉRIOS ON-PAGE (CONFORME SOLICITADO)
        checks = [
            (kw_norm in meta_txt_norm, "Keyword in Meta Description"),
            (kw_norm in normalize_text(url), "Keyword in URL"),
            (kw_norm in normalize_text(full_text)[:500], "Keyword at beginning of content"),
            (kw_norm in normalize_text(full_text), "Keyword in body text"),
            (any(kw_norm in normalize_text(h.text) for h in soup.find_all(['h2', 'h3'])), "Keyword in H2/H3"),
            (any(kw_norm in normalize_text(img.get('alt', '')) for img in soup.find_all('img')), "Keyword in Image Alts"),
            (len([l for l in soup.find_all('a', href=True) if urlparse(url).netloc in l['href']]) > 0, "Has Internal Links"),
            (len([l for l in soup.find_all('a', href=True) if urlparse(url).netloc not in l['href']]) > 0, "Has External Links"),
            (normalize_text(title_tag)[:30].find(kw_norm[:5]) != -1, "KW at start of Title"),
            (any(c.isdigit() for c in title_tag), "Number in Title (CTR boost)"),
            (any(p in normalize_text(title_tag) for p in ['best', 'guide', 'complete', 'tips', 'how']), "Power Word in Title"),
            (len(soup.find_all(['img', 'iframe'])) > 0, "Media Presence"),
            (word_count > 800, "Relevant Content (+800 words)"),
            (all(len(p.text.split()) < 70 for p in soup.find_all('p')[:3]), "Scanability (Short Paragraphs)"),
            (is_https, "HTTPS Security Protocol"),
            (has_favicon, "Favicon Present"),
            (has_compression, "Server Compression Active"),
            (is_indexable, "Indexing Allowed (Robots)"),
            (has_canonical, "Canonical Tag Configured"),
            (has_social, "Social Tags (Open Graph)")
        ]

        # --- CONSTRUÇÃO DO HTML ---
        report_html += '<div class="audit-card"><div class="card-header">INFO TÉCNICA & PLATAFORMA</div><div class="card-body">'
        report_html += r_row("CMS / Plataforma", platform, True)
        report_html += r_row("Tamanho do HTML", f"{len(res.content)/1024:.1f} KB")
        report_html += '</div></div>'
        
        # SEÇÃO 1: PERFORMANCE
        report_html += '<div class="audit-card"><div class="card-header">1. PERFORMANCE & CORE WEB VITALS</div><div class="card-body">'
        if ps_key and len(str(ps_key)) > 10:
            from engine import get_pagespeed_metrics
            ps = get_pagespeed_metrics(url, ps_key)
            if ps:
                numeric_scores["performance"] = ps.get('score', 0)
                vitals_data.update({k: ps.get(k, vitals_data[k]) for k in ["lcp", "fcp", "cls"]})
                report_html += r_row("Performance Score", f"{numeric_scores['performance']:.0f}/100")
                report_html += f'<p class="small text-muted mt-2">Core Metrics (UX):</p>'
                report_html += r_row("LCP (Largest Contentful Paint)", vitals_data["lcp"]["value"])
                report_html += r_row("FCP (First Contentful Paint)", vitals_data["fcp"]["value"])
                report_html += r_row("CLS (Cumulative Layout Shift)", vitals_data["cls"]["value"])
        else:
            report_html += '<p class="text-muted small">Google PageSpeed API não configurada.</p>'
        report_html += '</div></div>'

        # SEÇÃO 2: SEGURANÇA E MOBILE (ADICIONADA)
        
        report_html += '<div class="audit-card"><div class="card-header">2. SEGURANÇA & DISPOSITIVOS MÓVEIS</div><div class="card-body">'
        report_html += '<div class="row"><div class="col-md-6"><h6>Segurança</h6>'
        for item in sec_mob["details"]["sec"]:
            report_html += r_row(item["label"], item["status"], True)
        report_html += '</div><div class="col-md-6"><h6>Otimização Mobile</h6>'
        for item in sec_mob["details"]["mob"]:
            report_html += r_row(item["label"], item["status"], True)
        report_html += '</div></div></div></div>'

        # SEÇÃO 3: CHECKLIST ON-PAGE
        op_count = sum(1 for ok, _ in checks if ok)
        numeric_scores["on_page"] = (op_count / len(checks)) * 100
        report_html += '<div class="audit-card"><div class="card-header">3. CHECKLIST ON-PAGE</div><div class="card-body">'
        for ok, label in checks: 
            report_html += r_row(label, "Sim" if ok else "Não", True)
        report_html += '</div></div>'



        # SEÇÃO 4: SEMÂNTICA, AUTORIDADE E SCHEMA
        from engine import get_semantic_analysis, get_authority_metrics
        
        numeric_scores["on_page"] = (sum(1 for ok, _ in checks if ok) / len(checks)) * 100
        
        common, rich, r_score, _ = get_semantic_analysis(full_text)
        numeric_scores["semantic"] = r_score
        
        report_html += '<div class="audit-card"><div class="card-header">4. SEMÂNTICA E AUTORIDADE</div><div class="card-body">'
        report_html += r_row("Riqueza Vocabular", rich, True)
        if opr_key and len(str(opr_key)) > 10:
            auth = get_authority_metrics(url, opr_key)
            numeric_scores["authority"] = auth.get('da', 0)
            report_html += r_row("Autoridade do Domínio (DA)", f"{numeric_scores['authority']:.0f}/100")
        
        found_schemas = sorted(list(set(re.findall(r'["\']@type["\']\s*:\s*["\']([^"\']+)["\']', res.text))))
        numeric_scores["schema"] = 100 if found_schemas else 0
        report_html += r_row("Dados Estruturados", ", ".join(found_schemas[:3]) if found_schemas else "Nenhum detectado")
        report_html += '</div></div>'

        # RETORNO COM OS 5 VALORES
        return report_html, numeric_scores, words_list, vitals_data, sec_mob

    except Exception as e:
        error_msg = f"Erro crítico na auditoria: {str(e)}"
        print(error_msg)
        return f'<div class="alert alert-danger">{error_msg}</div>', numeric_scores, [], vitals_data, sec_mob

    

# --- BATALHA DE CONCORRENTES ---

def get_competitor_battle(url1, url2, keyword, serp_key, ps_key, opr_key):
    """Executa auditoria dupla e gera o comparativo de gap com tratamento de erros."""
    
    # 1. INICIALIZAÇÃO DE SEGURANÇA (Obrigatório)
    v_default = {
        "lcp": {"value": "N/A", "status": "gray"},
        "fcp": {"value": "N/A", "status": "gray"},
        "cls": {"value": "N/A", "status": "gray"}
    }
    v1 = v_default.copy()
    v2 = v_default.copy()
    h1, h2 = "", ""
    s1, s2 = {}, {}
    w1, w2 = [], []
    gap_html = "<div class='alert alert-info'>Análise de concorrência limitada (SERPAPI ausente).</div>"

    # 2. AUDITORIA SITE 1
    try:
        h1, s1, w1, v1 = get_advanced_audit(url1, keyword, ps_key, opr_key)
    except Exception as e:
        print(f"Erro na auditoria do Site 1: {e}")

    # 3. AUDITORIA SITE 2 (CONCORRENTE)
    try:
        h2, s2, w2, v2 = get_advanced_audit(url2, keyword, ps_key, opr_key)
    except Exception as e:
        print(f"Erro na auditoria do Site 2: {e}")

    # 4. LÓGICA DE GAP DE KEYWORDS
    if serp_key:
        try:
            # Removido o 'from engine import' pois já estamos no engine.py
            gap_html = get_keyword_gap(url1, url2, keyword, serp_key)
        except Exception as e:
            print(f"Erro no Keyword Gap: {e}")
            gap_html = "<div class='alert alert-warning'>Erro ao processar Gap de Keywords.</div>"

    # Retorna exatamente 9 valores
    return h1, s1, w1, h2, s2, w2, gap_html, v1, v2