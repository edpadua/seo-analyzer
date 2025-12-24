import requests
from bs4 import BeautifulSoup
import spacy
import json

# Load NLP Engine
try:
    nlp = spacy.load("pt_core_news_sm") # You can use "en_core_web_sm" for English NLP
except:
    nlp = None

GOOGLE_API_KEY = ""

def get_pagespeed_metrics(url):
    try:
        api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&category=PERFORMANCE&category=SEO"
        if GOOGLE_API_KEY:
            api_url += f"&key={GOOGLE_API_KEY}"
            
        response = requests.get(api_url, timeout=60)
        data = response.json()
        
        lighthouse = data.get('lighthouseResult', {})
        categories = lighthouse.get('categories', {})
        audits = lighthouse.get('audits', {})
        
        return {
            "perf_score": int(categories.get('performance', {}).get('score', 0) * 100),
            "seo_score": int(categories.get('seo', {}).get('score', 0) * 100),
            "lcp": audits.get('largest-contentful-paint', {}).get('displayValue', 'N/A'),
            "cls": audits.get('cumulative-layout-shift', {}).get('displayValue', 'N/A'),
            "tbt": audits.get('total-blocking-time', {}).get('displayValue', 'N/A')
        }
    except Exception as e:
        print(f"PageSpeed Error: {e}")
        return "disabled"

def extract_schema(soup):
    scripts = soup.find_all('script', type='application/ld+json')
    found = []
    for s in scripts:
        try:
            data = json.loads(s.string)
            found.append(data.get('@type'))
        except: continue
    return found if found else "None detected"

def get_advanced_audit(url, keyword):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        title = soup.title.string if soup.title else "N/A"
        h1 = soup.h1.get_text().strip() if soup.h1 else "N/A"
        schema = extract_schema(soup)
        
        entities = []
        if nlp:
            doc = nlp(soup.get_text()[:3000])
            entities = list(set([ent.text for ent in doc.ents if ent.label_ in ['ORG', 'LOC', 'PRODUCT']]))[:3]

        ps = get_pagespeed_metrics(url)
        
        return format_report(url, keyword, title, h1, schema, ps, entities)

    except Exception as e:
        return f"CRITICAL AUDIT ERROR: {str(e)}"

def format_report(url, kw, title, h1, schema, ps, entities):
    score = 0
    if kw.lower() in title.lower(): score += 50
    if ps != "disabled" and ps['perf_score'] > 50: score += 50

    report = f"""
ADVANCED SEO AUDIT REPORT

EXECUTIVE SUMMARY

Theoretical Score: {score}/100. Based on the correlation between the keyword {kw.upper()} and technical elements found on the URL.

TECHNICAL DIAGNOSIS AND PERFORMANCE

"""
    if ps != "disabled":
        report += f"Overall Score: {ps['perf_score']}\nCore Metrics: LCP at {ps['lcp']}, CLS at {ps['cls']} and TBT at {ps['tbt']}.\nTechnical Verdict: Analysis based on Web Vitals provided by Google API."
    else:
        report += "Performance metrics disabled for this analysis."

    report += f"""

STRUCTURED DATA ANALYSIS (SCHEMA.ORG)

Schema Status: {schema}
Rich Snippets Opportunity: Recommended implementation of FAQPage or Article to improve semantic visibility.

CONTENT & NLP AUDIT

Current Title Tag: {title}
Current H1: {h1}
Coherence Analysis: Keyword {kw} presence in Title and H1 is essential for the RankBrain algorithm.

ENTITIES & KEYWORD OPPORTUNITIES

- Related Term 1: {entities[0] if len(entities)>0 else 'N/A'}
- Related Term 2: {entities[1] if len(entities)>1 else 'N/A'}
- Related Term 3: {entities[2] if len(entities)>2 else 'N/A'}
- New H2 Question (FAQ): How does this service solve problems related to {kw}?

IMMEDIATE ACTION PLAN (HIGH PRIORITY)

1. Fix performance metrics if LCP is above 2.5s.
2. Optimize semantic density for terms identified by NLP.
3. Validate heading hierarchy to ensure only one H1 exists.
"""
    return report