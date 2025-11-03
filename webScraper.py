import streamlit as st, re, ssl, json, time, google.generativeai as genai
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlparse
from html.parser import HTMLParser
from collections import Counter
from datetime import datetime
import pandas as pd, plotly.express as px


# ---- Variable 1: G (Global config) ----

#WHOEVER IT MAY CONCERN ,I HAVE ALREADY DELETED THE KEY SO DONT WASTE YOUR TIME :D
#FOR JUDGES -> YOU HAVE TO PUT YOUR GEMINI KEY DOWN BELOW, THANK YOU

G = ["AIzaSyCFvfMQrrtRfU8bmhN52OZCSnD3S1IFe18", {'this', 'that', 'with', 'from', 'have', 'will', 'your', 'about', 'which', 'their', 'there'}]


genai.configure(api_key=G[0])
st.set_page_config(page_title="🌐 Smart Web Crawler", layout="wide")
st.title("🔍 Web Crawler & AI Analyzer")
st.caption("Crawl any website, extract info, analyze keywords, and generate an AI summary.")


# ---- Parser ----
class Parser(HTMLParser):
    def __init__(P):
        super().__init__()
        P.d = {'links': [], 'headings': [], 'images': [], 'text': [], 'emails': [], 'phones': []}
        P.t = None

    def handle_starttag(P, t, a):
        a = dict(a)
        if t == 'a' and 'href' in a:
            P.d['links'].append(a['href'])
        if t == 'img' and 'src' in a:
            P.d['images'].append({'src': a['src'], 'alt': a.get('alt', '')})
        if t in ('h1', 'h2', 'h3', 'h4'):
            P.t = t

    def handle_endtag(P, t):
        if t in ('h1', 'h2', 'h3', 'h4'):
            P.t = None

    def handle_data(P, x):
        x = x.strip()
        if not x:
            return
        if P.t:
            P.d['headings'].append({'level': P.t, 'text': x})
        P.d['text'].append(x)
        P.d['emails'] += re.findall(r'\b[\w\.-]+@[\w\.-]+\.\w+\b', x)
        P.d['phones'] += re.findall(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', x)



def scrape(G):  # Reuse G as parameter
    try:
        return urlopen(Request(G, headers={"User-Agent": "Mozilla/5.0"}), context=ssl._create_unverified_context(), timeout=10).read().decode('utf-8', 'ignore')
    except:
        return ""


def norm(G, X):  # Reuse G and X as parameters
    if not G or G.startswith(('#', 'js', 'mail', 'tel')):
        return None
    return f"{urlparse(urljoin(X, G)).scheme}://{urlparse(urljoin(X, G)).netloc}{urlparse(urljoin(X, G)).path}".rstrip('/')


def crawl(X, Z, D):  # Variable 2: X, Variable 3: Z, Variable 4: D
    X = [set(), [X], {}, urlparse(X).netloc, None, None, None]
    while X[1] and len(X[0]) < Z:
        X[4] = X[1].pop(0)
        if X[4] in X[0]:
            continue
        try:
            D(f"🔍 Crawling {len(X[0]) + 1}/{Z}: {X[4]}")
            X[5] = Parser()
            X[5].feed(scrape(X[4]))
            X[2][X[4]] = {
                'status': 'ok', 'data': X[5].d, 'links': len(X[5].d['links']),
                'images': len(X[5].d['images']), 'headings': len(X[5].d['headings']),
                'emails': list(set(X[5].d['emails'])), 'phones': list(set(X[5].d['phones'])),
                'text_len': sum(len(Z) for Z in X[5].d['text'])
            }
            for X[6] in X[5].d['links']:
                X[6] = norm(X[6], X[4])
                if X[6] and urlparse(X[6]).netloc == X[3] and X[6] not in X[0]:
                    X[1].append(X[6])
            X[0].add(X[4])
            time.sleep(0.5)
        except Exception as Z:  # Reuse Z for exception
            X[2][X[4]] = {'status': 'fail', 'err': str(Z)}
            X[0].add(X[4])
    return X[2], X[0]



def aggr(D):
    Z = {'links': [], 'headings': [], 'images': [], 'text': [], 'emails': [], 'phones': []}
    for X in D.values():
        if X.get('status') == 'ok':
            for D in Z:
                Z[D].extend(X['data'][D])
    return Z

def stats(D):  # Reuse D
    X = [' '.join(D['text']), None, None]
    X[1] = re.findall(r'\b[a-zA-Z]{4,}\b', X[0].lower())
    X[2] = [Z for Z in X[1] if Z not in G[1]]
    return {
        'tw': len(X[1]), 'uw': len(set(X[1])), 'top': Counter(X[2]).most_common(15),
        'em': len(set(D['emails'])), 'ph': len(set(D['phones']))
    }



def summary(X):  # Reuse X
    try:
        X = [X[:2000] + "…" if len(X) > 2000 else X, genai.GenerativeModel("gemini-2.0-flash")]
        return X[1].generate_content(f"Summarize the following website content clearly and concisely:\n\n{X[0]}").text.strip()
    except Exception as Z:
        return f"{Z}"


def save(G, X, D, Z):  # Reuse all as parameters
    X = [
        f"scrape_{re.sub(r'[^a-zA-Z0-9]', '_', G[:20])}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        {
            'meta': {'url': G, 'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                     'ok': len([_ for _ in X.values() if _.get('status') == 'ok']),'fail': len([_ for _ in X.values() if _.get('status') == 'fail'])},
            'stats': {'links': len(D['links']), 'images': len(D['images']),
                      'words': Z['tw'], 'unique': Z['uw'], 'emails': Z['em'], 'phones': Z['ph']},
            'keywords': Z['top'], 'emails': list(set(D['emails'])), 'phones': list(set(D['phones']))
        }
    ]
    with open(X[0], 'w', encoding='utf-8') as _:
        _.write(json.dumps(X[1], indent=2))
    return X[0]


# ---- Variable 5: Z (Main UI state) ----
Z = [st.text_input("🌍 Enter site URL"), st.slider("📄 Max pages", 1, 50, 5)]


if st.button("🚀 Crawl"):
    if not Z[0]:
        st.error("Enter valid URL")
    else:
        if not Z[0].startswith('http'):
            Z[0] = 'https://' + Z[0]
        Z.extend([st.empty(), None, None, None, None, None])
        
        with st.spinner("Crawling..."):
            Z[3] = crawl(Z[0], Z[1], lambda X: Z[2].info(X))
        st.success(f"✅ Done! {len(Z[3][1])} pages.")

        Z[4] = aggr(Z[3][0])
        Z[5] = stats(Z[4])
        Z[6] = save(Z[0], Z[3][0], Z[4], Z[5])

        st.subheader(" Stats");Z[7] = st.columns(4)
        Z[7][0].metric("Words", f"{Z[5]['tw']:,}")
        Z[7][1].metric("Unique", f"{Z[5]['uw']:,}")
        Z[7][2].metric("Emails", Z[5]['em'])
        Z[7][3].metric("Phones", Z[5]['ph'])

        st.subheader(" AI Summary")
        st.write(summary(' '.join(Z[4]['text'])))

        st.subheader("Top Keywords")
        st.plotly_chart(
            px.bar(pd.DataFrame(Z[5]['top'], columns=['Word', 'Count']),
                   x='Word', y='Count', color='Count', title="Top Keywords"),
            use_container_width=True
        )



        with st.expander("📧 Emails"):
            st.write(list(set(Z[4]['emails'])) or "None")

        with st.expander("📱 Phones"):
            st.write(list(set(Z[4]['phones'])) or "None")

        st.header("🗂️ Pages")
        # Variable 7: D, Variable 8: X (loop variables)
        for D, X in Z[3][0].items():
            if X.get('status') == 'ok':
                st.markdown(f" **{D}** — {X['links']} links, {X['images']} imgs, {X['headings']} headings")
                with st.expander(f"🔗 Links in {D}"):
                    st.write(X['data']['links'] or "None")
                with st.expander(f"📑 Headings in {D}"):
                    st.write(X['data']['headings'] or "None")
            else:
                st.markdown(f"**{D}** — {X.get('err')}")
