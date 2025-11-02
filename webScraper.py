import streamlit as st, json, time, re, ssl, io
from datetime import datetime
from collections import Counter
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlparse
from html.parser import HTMLParser
import pandas as pd, plotly.express as px
from openai import OpenAI

# ---- 8 globals only ----
KEY = "KEY"        # 1
CL = OpenAI(api_key=KEY) if KEY else None             # 2
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}  # 3
TR = 2000                                             # 4 truncate length for summary
TMOUT = 10                                            # 5 network timeout
DELAY = 0.5                                           # 6 crawl delay
FP = "fullscrape"                                     # 7 filename prefix
MAXDEF = 5                                            # 8 default pages

st.set_page_config(page_title="🔍 Web Crawler Dashboard", layout="wide")
st.title("🌐 Web Crawler & Analyzer with AI Summary")
st.caption("Crawl sites, inspect content, visualize keywords and get an AI summary.")

# ----- Parser -----
class EnhancedParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.data = {'links': [], 'headings': [], 'meta': {}, 'images': [], 'text': [], 'emails': [], 'phones': []}; self.tag = None
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'a' and 'href' in a: self.data['links'].append(a['href'])
        if tag == 'img' and 'src' in a: self.data['images'].append({'src': a['src'], 'alt': a.get('alt', '')})
        if tag == 'meta': self.data['meta'][a.get('name', a.get('property', 'unknown'))] = a.get('content', '')
        if tag in ('h1', 'h2', 'h3', 'h4'): self.tag = tag
    def handle_endtag(self, tag):
        if tag in ('h1', 'h2', 'h3', 'h4'): self.tag = None
    def handle_data(self, s):
        t = s.strip()
        if not t: return
        if self.tag: self.data['headings'].append({'level': self.tag, 'text': t})
        self.data['text'].append(t)
        for e in re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', t): self.data['emails'].append(e)
        for p in re.findall(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', t): self.data['phones'].append(p)

# ----- Core functions -----
def scrape(url, timeout=TMOUT):
    ctx = ssl._create_unverified_context()
    req = Request(url, headers=H)
    with urlopen(req, context=ctx, timeout=timeout) as r:
        b = r.read()
        try: return b.decode('utf-8')
        except UnicodeDecodeError: return b.decode('latin-1', errors='ignore')

def normalize_url(u, base):
    if not u or u.startswith(('#', 'javascript:', 'mailto:', 'tel:')): return None
    full = urljoin(base, u); p = urlparse(full)
    return f"{p.scheme}://{p.netloc}{p.path}".rstrip('/')

def crawl_site(start_url, max_pages=10, delay=DELAY, progress_callback=None):
    visited, to_visit, results = set(), [start_url], {}
    base_domain = urlparse(start_url).netloc
    while to_visit and len(visited) < max_pages:
        url = to_visit.pop(0)
        if url in visited: continue
        try:
            if progress_callback: progress_callback(f"🔍 Crawling [{len(visited)+1}/{max_pages}]: {url}")
            html = scrape(url)
            parser = EnhancedParser(); parser.feed(html)
            results[url] = {
                'status': 'success',
                'links': len(parser.data['links']),
                'images': len(parser.data['images']),
                'headings': len(parser.data['headings']),
                'emails': list(set(parser.data['emails'])),
                'phones': list(set(parser.data['phones'])),
                'text_length': sum(len(t) for t in parser.data['text']),
                'data': parser.data
            }
            for link in parser.data['links']:
                n = normalize_url(link, url)
                if n and urlparse(n).netloc == base_domain and n not in visited: to_visit.append(n)
            visited.add(url); time.sleep(delay)
        except Exception as e:
            results[url] = {'status': 'failed', 'error': str(e)}; visited.add(url)
    return results, visited

# ----- Analytics -----
def aggregate_data(results):
    all_data = {'links': [], 'headings': [], 'images': [], 'text': [], 'emails': [], 'phones': []}
    for url, r in results.items():
        if r.get('status') == 'success' and 'data' in r:
            d = r['data']
            for k in all_data: all_data[k].extend(d[k])
    return all_data

def analyze(aggregated):
    full_text = ' '.join(aggregated['text'])
    words = re.findall(r'\b[a-zA-Z]{4,}\b', full_text.lower())
    stop_words = {'this','that','with','from','have','will','your','about','which','their','there','would','could','should','been','more'}
    filtered = [w for w in words if w not in stop_words]
    return {
        'total_words': len(words),
        'unique_words': len(set(words)),
        'top_keywords': Counter(filtered).most_common(15),
        'total_emails': len(set(aggregated['emails'])),
        'total_phones': len(set(aggregated['phones']))
    }

# ----- AI summary (OpenAI client v1 style) -----
def generate_summary(text, max_tokens=150):
    if not CL: return "OpenAI API key not configured."
    payload = text[:TR] + " …" if len(text) > TR else text
    try:
        resp = CL.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"system","content":"You are an assistant that summarizes website content."},
                      {"role":"user","content":f"Please provide a concise summary of the following content:\n\n{payload}\n\nSummary:"}],
            max_tokens=max_tokens, temperature=0.3
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Summary generation error: {e}"

# ----- Export -----
def export_full_report(start_url, results, aggregated, analytics):
    report = {
        'metadata': {
            'start_url': start_url,
            'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'pages_crawled': len([r for r in results.values() if r['status'] == 'success']),
            'pages_failed': len([r for r in results.values() if r['status'] == 'failed'])
        },
        'site_statistics': {
            'total_links': len(aggregated['links']),
            'unique_links': len(set(aggregated['links'])),
            'total_images': len(aggregated['images']),
            'total_headings': len(aggregated['headings']),
            'total_words': analytics['total_words'],
            'unique_words': analytics['unique_words'],
            'emails_found': analytics['total_emails'],
            'phones_found': analytics['total_phones']
        },
        'top_keywords': [{'word': w, 'count': c} for w, c in analytics['top_keywords']],
        'pages': {u: {k: v for k, v in d.items() if k != 'data'} for u, d in results.items()},
        'all_emails': list(set(aggregated['emails']))[:20],
        'all_phones': list(set(aggregated['phones']))[:20],
        'sample_headings': aggregated['headings'][:30]
    }
    fn = f"{FP}_{re.sub(r'[^a-zA-Z0-9]', '_', start_url[:25])}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(fn, 'w', encoding='utf-8') as f: json.dump(report, f, indent=2, ensure_ascii=False)
    return fn

# ----- Streamlit UI -----
url = st.text_input("🌍 Enter starting URL (with or without https://)")
max_pages = st.slider("📄 Max pages to crawl", 1, 50, MAXDEF)

if st.button("🚀 Start Crawl"):
    if not url: st.error("Please enter a valid URL.")
    else:
        if not url.startswith('http'): url = 'https://' + url
        prog = st.empty()
        with st.spinner("Crawling in progress..."):
            results, visited = crawl_site(url, max_pages, progress_callback=lambda m: prog.info(m))
        st.success(f"✅ Crawl complete! Visited {len(visited)} pages.")
        aggregated = aggregate_data(results)
        analytics = analyze(aggregated)
        fn = export_full_report(url, results, aggregated, analytics)
        full_text_for_summary = " ".join(aggregated['text'])
        summary = generate_summary(full_text_for_summary)

        # Metrics
        st.header("📊 Site Summary")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🧾 Total Words", f"{analytics['total_words']:,}")
        c2.metric("🔠 Unique Words", f"{analytics['unique_words']:,}")
        c3.metric("📧 Emails Found", analytics['total_emails'])
        c4.metric("📱 Phones Found", analytics['total_phones'])

        # AI Summary
        st.subheader("📝 AI-Generated Summary")
        st.write(summary)

        # Keywords chart
        st.subheader("🔑 Top Keywords")
        df_keywords = pd.DataFrame(analytics['top_keywords'], columns=["Word", "Count"])
        fig_keywords = px.bar(df_keywords, x="Word", y="Count", color="Count", title="Most Frequent Keywords", color_continuous_scale="turbo")
        st.plotly_chart(fig_keywords, use_container_width=True)

        # Crawl status
        st.subheader("📈 Crawl Status Overview")
        success_count = len([r for r in results.values() if r['status'] == 'success'])
        fail_count = len([r for r in results.values() if r['status'] == 'failed'])
        fig_status = px.pie(values=[success_count, fail_count], names=["Successful", "Failed"], title="Crawl Success Rate")
        st.plotly_chart(fig_status, use_container_width=True)

        # Links vs Images scatter
        st.subheader("🔗 Links vs 🖼️ Images Per Page")
        page_data = [{'URL': u, 'Links': d.get('links', 0), 'Images': d.get('images', 0)} for u, d in results.items() if d['status'] == 'success']
        df_pages = pd.DataFrame(page_data)
        if not df_pages.empty:
            fig_links_images = px.scatter(df_pages, x="Links", y="Images", text="URL", color="Images", size="Links", title="Relationship Between Links & Images")
            st.plotly_chart(fig_links_images, use_container_width=True)

        # Download JSON
        with open(fn, "r", encoding="utf-8") as f:
            st.download_button(label="💾 Download Full Report (JSON)", data=f.read(), file_name=fn, mime="application/json")

        # Expanders
        with st.expander("📧 Extracted Emails"): st.write(list(set(aggregated['emails'])) or "None")
        with st.expander("📱 Extracted Phone Numbers"): st.write(list(set(aggregated['phones'])) or "None")

        # Pages overview
        st.header("🗂️ Pages Overview")
        for u, d in results.items():
            if d['status'] == 'success':
                st.markdown(f"✅ **{u}** — {d['links']} links, {d['images']} images, {d['text_length']} chars")
            else:
                st.markdown(f"❌ **{u}** — {d.get('error', 'Unknown error')}")