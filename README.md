# 🔍 Advanced SEO Auditor & NLP Specialist

A professional-grade SEO analysis tool built with Python, FastAPI, and NLP (Natural Language Processing). This application simulates a technical audit by a search engine specialist, analyzing webpage health and semantic relevance for a specific target keyword.

## 🚀 Key Features

- Forensic Technical Audit: Deep analysis of Title tags, H1 hierarchy, and metadata structure.
- Google PageSpeed Integration: Real-time Core Web Vitals (LCP, CLS, TBT) via the official Google Insights API.
- NLP Semantic Analysis: Leverages spaCy to detect entities (Organizations, Locations, Products) and evaluate topical depth.
- Schema.org Detection: Scans for JSON-LD structured data to find Rich Snippet opportunities.
- Forensic Reporting: A specialized "Terminal-style" output that provides a clear action plan for SEO improvement.

---

## 🛠️ Technical Stack

- Backend: FastAPI
- Parsing: BeautifulSoup4
- Intelligence: spaCy (NLP)
- API: Google PageSpeed Insights
- Frontend: Jinja2 Templates & Water.css

---

## 📋 Prerequisites

- Python 3.10 or higher.
- A Google Cloud API Key (for PageSpeed metrics).

## 🔧 Installation

1. Clone the repository:
   git clone https://github.com/your-username/seo-analyzer.git
   cd seo-analyzer

2. Setup Virtual Environment:
   python -m venv venv
   # Activate on Windows:
   .\venv\Scripts\activate
   # Activate on Mac/Linux:
   source venv/bin/activate

3. Install Dependencies:
   pip install fastapi uvicorn requests beautifulsoup4 jinja2 python-multipart spacy

4. Download NLP Model:
   python -m spacy download en_core_web_sm

## 🖥️ Running the App

Start the local server:
uvicorn main:app --reload

Open your browser at http://127.0.0.1:8000.

---

## 📖 How to Use

1. Input URL: Provide the full address (e.g., https://example.com).
2. Set Keyword: Enter the main keyword you wish to optimize for.
3. Analyze: The engine will fetch data from both the website and Google API (takes ~20-30 seconds).
4. Action Plan: Follow the generated "Immediate Action Plan" to improve your rankings.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---
*Developed as a tool for Technical SEOs and Developers.*
