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
# If using KeywordTracking model inside, make sure it's imported
import models

# --- UTILITIES AND NORMALIZATION ---

def extract_main_keyword(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Try Meta Keywords
        meta_k = soup.find("meta", attrs={"name": "keywords"})
        if meta_k and meta_k.get("content"):
            return meta_k.get("content").split(',')[0].strip()
        
        # 2. Try H1
        h1 = soup.find("h1")
        if h1:
            return h1.get_text().strip()

        # 3. EXTRACTION BY DENSITY (fallback)
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()
            
        text = soup.get_text().lower()
        words = re.findall(r'\b\w{4,}\b', text)
        
        # Stopwords list (Portuguese common words to ignore)
        stopwords = ['sobre', 'mais', 'para', 'como', 'fazer', 'página', 'todos', 'direitos']
        filtered_words = [w for w in words if w not in stopwords]
        
        if filtered_words:
            most_common = Counter(filtered_words).most_common(1)
            return most_common[0][0].capitalize()

        return "SEO Analysis"
    except:
        return "SEO Analysis"

def normalize_text(text):
    """Normalize text by removing accents and special characters."""
    if not text: return ""
    text = text.lower().replace("-", " ").replace("_", " ")
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
    return " ".join(text.split())

def get_semantic_analysis(text):
    """Analyze vocabulary richness and return a score from 0 to 100."""
    stops = set(['this', 'that', 'these', 'those', 'for', 'with', 'more', 'very', 'by', 'his', 'her', 'how', 'about', 'all', 'where', 'when', 'who'])
    words = re.findall(r'\b\w{4,}\b', text.lower())
    filtered = [w for w in words if w not in stops]
    common = Counter(filtered).most_common(8)
    
    unique_ratio = len(set(words)) / len(words) if words else 0
    
    if unique_ratio > 0.5:
        richness = "High"
        richness_score = 100
    elif unique_ratio > 0.3:
        richness = "Medium"
        richness_score = 70
    else:
        richness = "Low"
        richness_score = 40
        
    return common, richness, richness_score, filtered

# --- EXTERNAL METRICS (APIs) ---

def get_authority_metrics(url, opr_key):
    """Get authority metrics via Open Page Rank."""
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
                "status": "Strong" if da > 30 else "Beginner"
            }
    except: pass
    return {"pr": "1.0/10", "gr": "#N/A", "da": 10, "status": "Beginner"}

def get_pagespeed_metrics(url, api_key):
    try:
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
    """Fetch ranking data from SerpApi and compare both domains."""
    params = {
        "engine": "google",
        "q": keyword,
        "api_key": api_key
    }
    
    try:
        response = requests.get("https://serpapi.com/search", params=params, timeout=15)
        data = response.json()
        results = data.get("organic_results", [])
        
        pos1, pos2 = "N/A", "N/A"
        domain1 = urlparse(url1).netloc.replace("www.", "")
        domain2 = urlparse(url2).netloc.replace("www.", "")

        for idx, res in enumerate(results):
            link = res.get("link", "")
            if domain1 in link: pos1 = idx + 1
            if domain2 in link: pos2 = idx + 1

        return f"""
        <div class='audit-card'>
            <div class='card-header'>Rank Tracker - Direct Competition</div>
            <div class='card-body'>
                <p>{domain1} Position: <strong>{pos1}{"º" if pos1 != "N/A" else ""}</strong></p>
                <p>{domain2} Position: <strong>{pos2}{"º" if pos2 != "N/A" else ""}</strong></p>
            </div>
        </div>
        """
    except Exception as e:
        return f"<p>Error processing SerpApi: {e}</p>"

def update_rank_history(db: Session, user_id: int, url: str, keyword: str, serp_key: str):
    """
    Query the real Google position of the URL and store it in the database history.
    """
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

        current_pos = 0
        
        for res in results:
            if domain in res.get("link", ""):
                current_pos = res.get("position")
                break
        
        from models import KeywordTracking
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
        print(f"Error updating ranking: {e}")
        return None

# --- ARTIFICIAL INTELLIGENCE ---

def get_ai_seo_insights(keyword, content_snippet, provider, api_key, model):
    if not api_key or not provider: 
        return None
    
    provider = provider.lower()
    prompt = f"""
    Analyze the keyword "{keyword}" and this content summary: "{content_snippet[:1000]}".
    Return ONLY a strict JSON (no markdown, no explanations) with this structure:
    {{
      "suggested_title": "SEO Title",
      "suggested_meta": "Meta description",
      "content_analysis": "Strategic analysis"
    }}
    """

    try:
        if 'gemini' in provider:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model_ai = genai.GenerativeModel(model or "gemini-1.5-flash")
            response = model_ai.generate_content(prompt)
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
        print(f"--- AI ERROR ---: {e}")
        return None

def extract_semantic_terms(text, limit=15):
    """Extract relevant terms ignoring common stop words."""
    stop_words = {'with', 'for', 'a', 'about', 'more', 'very', 'by', 'his', 'her', 'how', 'where', 'which'}
    
    words = re.findall(r'\b[a-z]{4,15}\b', text.lower())
    filtered_words = [w for w in words if w not in stop_words]
    
    return [term for term, count in Counter(filtered_words).most_common(limit)]

def get_ai_content_strategy(url1, text1, url2, text2, keyword, ai_client, model):
    """Generate Topic Gap, Meta Tags suggestions and LSI keywords."""
    terms1 = extract_semantic_terms(text1)
    terms2 = extract_semantic_terms(text2)
    
    prompt = f"""
    Analyze content SEO for the keyword: "{keyword}"
    My Site ({url1}): {", ".join(terms1)}
    Competitor ({url2}): {", ".join(terms2)}
    
    Respond with strict JSON only:
    {{
        "topic_gap": "list of 3 terms the competitor uses and I don't",
        "lsi_keywords": ["term1", "term2", "term3", "term4", "term5"], 
        "meta_suggestions": [
            {{"title": "Suggestion 1", "desc": "Meta desc 1"}},
            {{"title": "Suggestion 2", "desc": "Meta desc 2"}},
            {{"title": "Suggestion 3", "desc": "Meta desc 3"}}
        ],
        "content_advice": "Quick strategic tip"
    }}
    """
    
    try:
        response = ai_client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": "You are an SEO NLP expert."},
                      {"role": "user", "content": prompt}],
            response_format={ "type": "json_object" }
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"error": str(e)}

# --- MAIN TECHNICAL AUDIT ---

def check_security_and_mobile(url):
    """Check if the site is secure (HTTPS) and has basic mobile settings."""
    results = {
        "has_ssl": url.startswith("https"),
        "has_viewport": False,
        "is_compressed": False
    }
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results["has_viewport"] = bool(soup.find("meta", attrs={"name": "viewport"}))
        
        encoding = response.headers.get("Content-Encoding", "").lower()
        results["is_compressed"] = any(x in encoding for x in ["gzip", "br", "deflate"])
    except:
        pass
    return results

def detect_cms(soup, html_text, headers):
    """Detect platform/CMS with advanced heuristics."""
    html_low = html_text.lower()
    
    gen = soup.find("meta", attrs={"name": "generator"})
    gen_content = gen.get("content", "").lower() if gen else ""
    
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

    if "_next/static" in html_low: return "Next.js"
    if "gatsby-static" in html_low: return "Gatsby"
    if "react" in html_low and "data-reactroot" in html_low: return "React.js Custom"
    
    if "magento" in html_low or "mage/" in html_low: return "Magento"
    if "joomla" in gen_content: return "Joomla"
    if "drupal" in gen_content: return "Drupal"
    
    return "Custom / Undetected"

def get_advanced_audit(url, keyword, ps_key=None, opr_key=None):
    """
    Run complete SEO audit including Core Web Vitals, On-page Checklist, 
    Semantic Analysis, Security and Mobile Optimization.
    Returns: (report_html, numeric_scores, words_list, vitals_data, sec_mob)
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
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
            positives = ["Yes", "✅", "Strong", "High", "Correct", "Active", "WordPress", 
                         "Shopify", "VTEX", "Nuvemshop", "Tray", "RD Station", "Wix", 
                         "Webflow", "HubSpot", "Next.js", "Gatsby", "Magento"]
            
            is_ok = any(x.lower() in str(val).lower() for x in positives)
            cl = "tag-sim" if is_ok else "tag-nao"
            return f'<div class="data-row"><span class="label">{label}:</span><span class="tag {cl}">{val}</span></div>'
        return f'<div class="data-row"><span class="label">{label}:</span><span class="value">{val}</span></div>'

    try:
        res = requests.get(url, headers=headers, timeout=30)
        res.encoding = res.apparent_encoding 
        soup = BeautifulSoup(res.text, 'html.parser')

        platform = detect_cms(soup, res.text, res.headers)
        
        soup_c = BeautifulSoup(res.text, 'html.parser')
        for s in soup_c(["script", "style", "nav", "footer", "header", "aside", "form"]): 
            s.decompose()
        
        full_text = soup_c.get_text()
        words_list = re.findall(r'\w+', full_text.lower())
        word_count = len(words_list)
        
        kw_norm = normalize_text(keyword)
        
        title_tag = soup.title.string.strip() if soup.title else ""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        meta_content = meta_desc['content'] if meta_desc and meta_desc.has_attr('content') else ""
        meta_txt_norm = normalize_text(meta_content)
        
        is_https = url.startswith("https")
        has_favicon = soup.find("link", rel=re.compile(r"icon", re.I)) is not None
        encoding_header = res.headers.get('Content-Encoding', '').lower()
        has_compression = any(c in encoding_header for c in ['gzip', 'br', 'deflate', 'zstd'])
        
        robots = soup.find("meta", attrs={"name": "robots"})
        is_indexable = "noindex" not in (robots["content"].lower() if robots and robots.has_attr("content") else "")
        has_canonical = soup.find("link", rel="canonical") is not None
        has_social = soup.find("meta", property=re.compile(r"^og:")) is not None

        h = res.headers
        sec_items = [
            (is_https, "HTTPS Protocol"),
            ("Strict-Transport-Security" in h, "HSTS Active"),
            ("X-Frame-Options" in h, "Clickjacking Protection"),
            ("X-Content-Type-Options" in h, "MIME Sniffing Protection")
        ]
        
        viewport = soup.find("meta", attrs={"name": "viewport"})
        mob_items = [
            (viewport is not None, "Viewport Meta Defined"),
            ("width=device-width" in (viewport["content"] if viewport else ""), "Device-Width Adjustment"),
            ("@media" in res.text, "Media Queries Detected"),
            (len(soup.find_all("picture")) > 0 or "srcset" in res.text, "Responsive Images")
        ]

        sec_mob["security_score"] = (sum(1 for ok, _ in sec_items if ok) / len(sec_items)) * 100
        sec_mob["mobile_score"] = (sum(1 for ok, _ in mob_items if ok) / len(mob_items)) * 100
        sec_mob["details"]["sec"] = [{"label": l, "status": "Yes" if ok else "No"} for ok, l in sec_items]
        sec_mob["details"]["mob"] = [{"label": l, "status": "Yes" if ok else "No"} for ok, l in mob_items]

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

        # --- HTML REPORT BUILDING ---
        report_html += '<div class="audit-card"><div class="card-header">TECHNICAL INFO & PLATFORM</div><div class="card-body">'
        report_html += r_row("CMS / Platform", platform, True)
        report_html += r_row("HTML Size", f"{len(res.content)/1024:.1f} KB")
        report_html += '</div></div>'
        
        report_html += '<div class="audit-card"><div class="card-header">1. PERFORMANCE & CORE WEB VITALS</div><div class="card-body">'
        if ps_key and len(str(ps_key)) > 10:
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
            report_html += '<p class="text-muted small">Google PageSpeed API not configured.</p>'
        report_html += '</div></div>'

        report_html += '<div class="audit-card"><div class="card-header">2. SECURITY & MOBILE OPTIMIZATION</div><div class="card-body">'
        report_html += '<div class="row"><div class="col-md-6"><h6>Security</h6>'
        for item in sec_mob["details"]["sec"]:
            report_html += r_row(item["label"], item["status"], True)
        report_html += '</div><div class="col-md-6"><h6>Mobile Optimization</h6>'
        for item in sec_mob["details"]["mob"]:
            report_html += r_row(item["label"], item["status"], True)
        report_html += '</div></div></div></div>'

        op_count = sum(1 for ok, _ in checks if ok)
        numeric_scores["on_page"] = (op_count / len(checks)) * 100
        report_html += '<div class="audit-card"><div class="card-header">3. ON-PAGE CHECKLIST</div><div class="card-body">'
        for ok, label in checks: 
            report_html += r_row(label, "Yes" if ok else "No", True)
        report_html += '</div></div>'

        common, rich, r_score, _ = get_semantic_analysis(full_text)
        numeric_scores["semantic"] = r_score
        
        report_html += '<div class="audit-card"><div class="card-header">4. SEMANTIC & AUTHORITY</div><div class="card-body">'
        report_html += r_row("Vocabulary Richness", rich, True)
        if opr_key and len(str(opr_key)) > 10:
            auth = get_authority_metrics(url, opr_key)
            numeric_scores["authority"] = auth.get('da', 0)
            report_html += r_row("Domain Authority (DA)", f"{numeric_scores['authority']:.0f}/100")
        
        found_schemas = sorted(list(set(re.findall(r'["\']@type["\']\s*:\s*["\']([^"\']+)["\']', res.text))))
        numeric_scores["schema"] = 100 if found_schemas else 0
        report_html += r_row("Structured Data", ", ".join(found_schemas[:3]) if found_schemas else "None detected")
        report_html += '</div></div>'

        return report_html, numeric_scores, words_list, vitals_data, sec_mob

    except Exception as e:
        error_msg = f"Critical audit error: {str(e)}"
        print(error_msg)
        return f'<div class="alert alert-danger">{error_msg}</div>', numeric_scores, [], vitals_data, sec_mob

# --- COMPETITOR BATTLE ---

def get_competitor_battle(url1, url2, keyword, serp_key, ps_key, opr_key):
    """Run dual audit and generate comparison with error handling."""
    
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
    gap_html = "<div class='alert alert-info'>Competitor analysis limited (SERPAPI not available).</div>"

    try:
        h1, s1, w1, v1_temp = get_advanced_audit(url1, keyword, ps_key, opr_key)
        v1.update(v1_temp)
    except Exception as e:
        print(f"Error auditing Site 1: {e}")

    try:
        h2, s2, w2, v2_temp = get_advanced_audit(url2, keyword, ps_key, opr_key)
        v2.update(v2_temp)
    except Exception as e:
        print(f"Error auditing Site 2: {e}")

    if serp_key:
        try:
            gap_html = get_keyword_gap(url1, url2, keyword, serp_key)
        except Exception as e:
            print(f"Keyword Gap error: {e}")
            gap_html = "<div class='alert alert-warning'>Error processing Keyword Gap.</div>"

    return h1, s1, w1, h2, s2, w2, gap_html, v1, v2