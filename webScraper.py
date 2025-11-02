import streamlit as st, re, ssl, json, time, google.generativeai as genai
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlparse
from html.parser import HTMLParser
from collections import Counter
from datetime import datetime
import pandas as pd, plotly.express as px
from dotenv import load_dotenv
import os
# ---- 8 Globals ----
load_dotenv()  # Load environment variables from .env file
GEMINI_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GEMINI_KEY)

H = {"User-Agent": "Mozilla/5.0"}
TR = 2000
TMOUT = 10
DELAY = 0.5
FP = "scrape"
MAXDEF = 5

st.set_page_config(page_title="🌐 Smart Web Crawler", layout="wide")
st.title("🔍 Web Crawler & AI Analyzer")
st.caption("Crawl any website, extract info, analyze keywords, and generate an AI summary.")

# ---- Parser ----
class Parser(HTMLParser):
    def __init__(s):
        super().__init__()
        s.d = {'links': [], 'headings': [], 'images': [], 'text': [], 'emails': [], 'phones': []}
        s.t = None

    def handle_starttag(s, t, a):
        a = dict(a)
        if t == 'a' and 'href' in a:
            s.d['links'].append(a['href'])
        if t == 'img' and 'src' in a:
            s.d['images'].append({'src': a['src'], 'alt': a.get('alt', '')})
        if t in ('h1', 'h2', 'h3', 'h4'):
            s.t = t

    def handle_endtag(s, t):
        if t in ('h1', 'h2', 'h3', 'h4'):
            s.t = None

    def handle_data(s, x):
        x = x.strip()
        if not x:
            return
        if s.t:
            s.d['headings'].append({'level': s.t, 'text': x})
        s.d['text'].append(x)
        s.d['emails'] += re.findall(r'\b[\w\.-]+@[\w\.-]+\.\w+\b', x)
        s.d['phones'] += re.findall(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', x)

# ---- Core ----
def scrape(u):
    try:
        ctx = ssl._create_unverified_context()
        return urlopen(Request(u, headers=H), context=ctx, timeout=TMOUT).read().decode('utf-8', 'ignore')
    except:
        return ""

def norm(u, b):
    if not u or u.startswith(('#', 'js', 'mail', 'tel')):
        return None
    f = urljoin(b, u)
    p = urlparse(f)
    return f"{p.scheme}://{p.netloc}{p.path}".rstrip('/')

def crawl(start, maxp, cb):
    vis, to_do, res = set(), [start], {}
    dom = urlparse(start).netloc
    while to_do and len(vis) < maxp:
        u = to_do.pop(0)
        if u in vis:
            continue
        try:
            cb(f"🔍 Crawling {len(vis) + 1}/{maxp}: {u}")
            h = scrape(u)
            p = Parser()
            p.feed(h)
            res[u] = {
                'status': 'ok',
                'data': p.d,
                'links': len(p.d['links']),
                'images': len(p.d['images']),
                'headings': len(p.d['headings']),
                'emails': list(set(p.d['emails'])),
                'phones': list(set(p.d['phones'])),
                'text_len': sum(len(t) for t in p.d['text'])
            }
            for l in p.d['links']:
                n = norm(l, u)
                if n and urlparse(n).netloc == dom and n not in vis:
                    to_do.append(n)
            vis.add(u)
            time.sleep(DELAY)
        except Exception as e:
            res[u] = {'status': 'fail', 'err': str(e)}
            vis.add(u)
    return res, vis

# ---- Analysis ----
def aggr(r):
    d = {'links': [], 'headings': [], 'images': [], 'text': [], 'emails': [], 'phones': []}
    for v in r.values():
        if v.get('status') == 'ok':
            for k in d:
                d[k].extend(v['data'][k])
    return d

def stats(d):
    t = ' '.join(d['text'])
    w = re.findall(r'\b[a-zA-Z]{4,}\b', t.lower())
    sw = {'this', 'that', 'with', 'from', 'have', 'will', 'your', 'about', 'which', 'their', 'there'}
    f = [x for x in w if x not in sw]
    return {
        'tw': len(w),
        'uw': len(set(w)),
        'top': Counter(f).most_common(15),
        'em': len(set(d['emails'])),
        'ph': len(set(d['phones']))
    }

# ---- AI Summary (Gemini) ----
def summary(t):
    try:
        s = t[:TR] + "…" if len(t) > TR else t
        model = genai.GenerativeModel("gemini-2.0-flash")  # you can also use "gemini-pro"
        prompt = f"Summarize the following website content clearly and concisely:\n\n{s}"
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"❌ {e}"

# ---- Export ----
def save(url, r, a, s):
    fn = f"{FP}_{re.sub(r'[^a-zA-Z0-9]', '_', url[:20])}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out = {
        'meta': {'url': url, 'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                 'ok': len([x for x in r.values() if x.get('status') == 'ok']),
                 'fail': len([x for x in r.values() if x.get('status') == 'fail'])},
        'stats': {'links': len(a['links']), 'images': len(a['images']),
                  'words': s['tw'], 'unique': s['uw'], 'emails': s['em'], 'phones': s['ph']},
        'keywords': s['top'], 'emails': list(set(a['emails'])), 'phones': list(set(a['phones']))
    }
    with open(fn, 'w', encoding='utf-8') as f:
        f.write(json.dumps(out, indent=2))
    return fn

# ---- UI ----
url = st.text_input("🌍 Enter site URL")
maxp = st.slider("📄 Max pages", 1, 50, MAXDEF)

if st.button("🚀 Crawl"):
    if not url:
        st.error("Enter valid URL")
    else:
        if not url.startswith('http'):
            url = 'https://' + url
        prog = st.empty()
        with st.spinner("Crawling..."):
            r, v = crawl(url, maxp, lambda m: prog.info(m))
        st.success(f"✅ Done! {len(v)} pages.")
        a = aggr(r)
        s = stats(a)
        fn = save(url, r, a, s)

        st.subheader("📊 Stats")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Words", f"{s['tw']:,}")
        c2.metric("Unique", f"{s['uw']:,}")
        c3.metric("Emails", s['em'])
        c4.metric("Phones", s['ph'])

        st.subheader("📝 AI Summary")
        st.write(summary(' '.join(a['text'])))

        st.subheader("🔑 Top Keywords")
        df = pd.DataFrame(s['top'], columns=['Word', 'Count'])
        fig = px.bar(df, x='Word', y='Count', color='Count', title="Top Keywords")
        st.plotly_chart(fig, width='stretch')

        with open(fn, 'r', encoding='utf-8') as fh:
            st.download_button("💾 Download Report", fh.read(), file_name=fn, mime="application/json")

        with st.expander("📧 Emails"):
            st.write(list(set(a['emails'])) or "None")

        with st.expander("📱 Phones"):
            st.write(list(set(a['phones'])) or "None")

        st.header("🗂️ Pages")
        for u, d in r.items():
            if d.get('status') == 'ok':
                st.markdown(f"✅ **{u}** — {d['links']} links, {d['images']} imgs, {d['headings']} headings")
                with st.expander(f"🔗 Links in {u}"):
                    st.write(d['data']['links'] or "None")
                with st.expander(f"📑 Headings in {u}"):
                    st.write(d['data']['headings'] or "None")
            else:
                st.markdown(f"❌ **{u}** — {d.get('err')}")