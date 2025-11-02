import streamlit as st
import json
import time
from datetime import datetime
from collections import Counter
import re
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlparse
from urllib.error import URLError, HTTPError
import ssl
from html.parser import HTMLParser
import io
import pandas as pd
from openai import OpenAI

import plotly.express as px
import openai  # ← New import

# Ensure you have your OpenAI API key set:
# export OPENAI_API_KEY="your_key_here"
openai.api_key = "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"

# ---------------------- HTML PARSER ---------------------- #
class EnhancedParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.data = {'links': [], 'headings': [], 'meta': {}, 'images': [], 
                     'text': [], 'emails': [], 'phones': []}
        self.tag = None
    
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == 'a' and 'href' in attrs_dict:
            self.data['links'].append(attrs_dict['href'])
        elif tag == 'img' and 'src' in attrs_dict:
            self.data['images'].append({'src': attrs_dict['src'], 
                                       'alt': attrs_dict.get('alt', 'N/A')})
        elif tag == 'meta':
            self.data['meta'][attrs_dict.get('name', attrs_dict.get('property', 'unknown'))] = \
                attrs_dict.get('content', '')
        elif tag in ['h1', 'h2', 'h3', 'h4']:
            self.tag = tag
    
    def handle_endtag(self, tag):
        if tag in ['h1', 'h2', 'h3', 'h4']:
            self.tag = None
    
    def handle_data(self, content):
        stripped = content.strip()
        if stripped:
            if self.tag:
                self.data['headings'].append({'level': self.tag, 'text': stripped})
            self.data['text'].append(stripped)
            for email in re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', stripped):
                self.data['emails'].append(email)
            for phone in re.findall(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', stripped):
                self.data['phones'].append(phone)

# ---------------------- CORE SCRAPER ---------------------- #
def scrape(url, timeout=10):
    ctx = ssl._create_unverified_context()
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    })
    with urlopen(req, context=ctx, timeout=timeout) as response:
        data = response.read()
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            return data.decode('latin-1', errors='ignore')

def normalize_url(url, base_url):
    if not url or url.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
        return None
    full_url = urljoin(base_url, url)
    parsed = urlparse(full_url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/')

def crawl_site(start_url, max_pages=10, delay=0.5, progress_callback=None):
    visited, to_visit, results = set(), [start_url], {}
    base_domain = urlparse(start_url).netloc
    
    while to_visit and len(visited) < max_pages:
        url = to_visit.pop(0)
        if url in visited:
            continue
        
        try:
            if progress_callback:
                progress_callback(f"🔍 Crawling [{len(visited)+1}/{max_pages}]: {url}")
            
            html = scrape(url)
            parser = EnhancedParser()
            parser.feed(html)
            
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
                normalized = normalize_url(link, url)
                if normalized and urlparse(normalized).netloc == base_domain and normalized not in visited:
                    to_visit.append(normalized)
            
            visited.add(url)
            time.sleep(delay)
            
        except Exception as e:
            results[url] = {'status': 'failed', 'error': str(e)}
            visited.add(url)
    
    return results, visited

# ---------------------- ANALYTICS ---------------------- #
def aggregate_data(results):
    all_data = {'links': [], 'headings': [], 'images': [], 'text': [], 'emails': [], 'phones': []}
    for url, result in results.items():
        if result['status'] == 'success' and 'data' in result:
            data = result['data']
            for key in all_data:
                all_data[key].extend(data[key])
    return all_data

def analyze(aggregated):
    full_text = ' '.join(aggregated['text'])
    words = re.findall(r'\b[a-zA-Z]{4,}\b', full_text.lower())
    stop_words = {'this','that','with','from','have','will','your','about','which','their','there','would','could','should','been','more'}
    filtered = [w for w in words if w not in stop_words]
    word_freq = Counter(filtered).most_common(15)
    return {
        'total_words': len(words),
        'unique_words': len(set(words)),
        'top_keywords': word_freq,
        'total_emails': len(set(aggregated['emails'])),
        'total_phones': len(set(aggregated['phones']))
    }

# ---------------------- NEW: SUMMARIZATION FUNCTION ---------------------- #
def generate_summary(text: str, max_tokens: int = 150) -> str:
    """
    Uses OpenAI API to summarize the given text.
    Note: Text may need to be truncated if too long.
    """
    if not openai.api_key:
        return "OpenAI API key not found – summary unavailable."
    
    # truncate long text to avoid token limits
    max_length = 2000  # adjust based on model limits
    if len(text) > max_length:
        text = text[:max_length] + " …"
    
    prompt = f"Please provide a concise summary of the following content:\n\n{text}\n\nSummary:"
    try:
        client = OpenAI(api_key="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")

        response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful summarizer."},
            {"role": "user", "content": "Summarize this article text: <your_text_here>"}
        ]
        )

        summary = response.choices[0].message.content
        return summary
    except Exception as e:
        return f"Summary generation error: {str(e)}"

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
        'pages': {url: {k: v for k, v in data.items() if k != 'data'} for url, data in results.items()},
        'all_emails': list(set(aggregated['emails']))[:20],
        'all_phones': list(set(aggregated['phones']))[:20],
        'sample_headings': aggregated['headings'][:30]
    }
    filename = f"fullscrape_{re.sub(r'[^a-zA-Z0-9]', '_', start_url[:25])}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return filename

# ---------------------- STREAMLIT UI ---------------------- #
st.set_page_config(page_title="🔍 Web Crawler Dashboard", layout="wide", initial_sidebar_state="expanded")
st.title("🌐 Web Crawler & Analyzer with AI Summary")
st.caption("An interactive crawler + analyzer + summary generator for any website.")

url = st.text_input("🌍 Enter starting URL (with or without https://)")
max_pages = st.slider("📄 Max pages to crawl", min_value=1, max_value=50, value=5)

if st.button("🚀 Start Crawl"):
    if not url:
        st.error("Please enter a valid URL.")
    else:
        if not url.startswith('http'):
            url = 'https://' + url

        progress_area = st.empty()
        with st.spinner("Crawling in progress..."):
            results, visited = crawl_site(
                url, 
                max_pages=max_pages, 
                progress_callback=lambda msg: progress_area.info(msg)
            )

        st.success(f"✅ Crawl complete! Visited {len(visited)} pages.")

        aggregated = aggregate_data(results)
        analytics = analyze(aggregated)
        filename = export_full_report(url, results, aggregated, analytics)

        # Generate summary of all scraped text
        full_text_for_summary = " ".join(aggregated['text'])
        summary = generate_summary(full_text_for_summary)

        # ---- Summary Metrics ---- #
        st.header("📊 Site Summary")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🧾 Total Words", f"{analytics['total_words']:,}")
        col2.metric("🔠 Unique Words", f"{analytics['unique_words']:,}")
        col3.metric("📧 Emails Found", analytics['total_emails'])
        col4.metric("📱 Phones Found", analytics['total_phones'])

        # ---- AI-Generated Summary ---- #
        st.subheader("📝 AI-Generated Summary")
        st.write(summary)

        # ---- Keyword Graph ---- #
        st.subheader("🔑 Top Keywords")
        df_keywords = pd.DataFrame(analytics['top_keywords'], columns=["Word", "Count"])
        fig_keywords = px.bar(df_keywords, x="Word", y="Count", color="Count",
                              title="Most Frequent Keywords",
                              color_continuous_scale="turbo")
        st.plotly_chart(fig_keywords, use_container_width=True)

        # ---- Page Success Chart ---- #
        st.subheader("📈 Crawl Status Overview")
        success_count = len([r for r in results.values() if r['status'] == 'success'])
        fail_count = len([r for r in results.values() if r['status'] == 'failed'])
        fig_status = px.pie(values=[success_count, fail_count], 
                            names=["Successful", "Failed"], 
                            title="Crawl Success Rate")
        st.plotly_chart(fig_status, use_container_width=True)

        # ---- Links vs Images ---- #
        st.subheader("🔗 Links vs 🖼️ Images Per Page")
        page_data = [{'URL': u, 'Links': d.get('links', 0), 'Images': d.get('images', 0)} 
                     for u, d in results.items() if d['status'] == 'success']
        df_pages = pd.DataFrame(page_data)
        if not df_pages.empty:
            fig_links_images = px.scatter(df_pages, x="Links", y="Images", text="URL",
                                          color="Images", size="Links",
                                          title="Relationship Between Links & Images")
            st.plotly_chart(fig_links_images, use_container_width=True)

        # ---- Download JSON ---- #
        with open(filename, "r", encoding="utf-8") as f:
            st.download_button(
                label="💾 Download Full Report (JSON)",
                data=f.read(),
                file_name=filename,
                mime="application/json"
            )

        # ---- Emails and Phones ---- #
        with st.expander("📧 Extracted Emails"):
            st.write(list(set(aggregated['emails'])) or "None")

        with st.expander("📱 Extracted Phone Numbers"):
            st.write(list(set(aggregated['phones'])) or "None")

        # ---- Pages Overview ---- #
        st.header("🗂️ Pages Overview")
        for u, d in results.items():
            if d['status'] == 'success':
                st.markdown(f"✅ **{u}** — {d['links']} links, {d['images']} images, {d['text_length']} chars")
            else:
                st.markdown(f"❌ **{u}** — {d.get('error', 'Unknown error')}") 