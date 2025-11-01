from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urljoin, urlparse
import ssl, re, json, time
from collections import Counter
from datetime import datetime


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


def scrape(url, timeout=10):
    ctx = ssl._create_unverified_context()
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    })
    with urlopen(req, context=ctx, timeout=timeout) as response:
        data = response.read()
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            return data.decode('latin-1', errors='ignore')


def normalize_url(url, base_url):
    if not url or url.startswith('#') or url.startswith('javascript:') or url.startswith('mailto:') or url.startswith('tel:'):
        return None
    full_url = urljoin(base_url, url)
    parsed = urlparse(full_url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/')


def crawl_site(start_url, max_pages=10, delay=0.5):
    visited, to_visit, results = set(), [start_url], {}
    base_domain = urlparse(start_url).netloc
    
    while to_visit and len(visited) < max_pages:
        url = to_visit.pop(0)
        if url in visited:
            continue
        
        try:
            print(f"  🔍 Crawling [{len(visited)+1}/{max_pages}]: {url[:60]}...")
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


def aggregate_data(results):
    all_data = {'links': [], 'headings': [], 'images': [], 'text': [], 'emails': [], 'phones': []}
    
    for url, result in results.items():
        if result['status'] == 'success' and 'data' in result:
            data = result['data']
            all_data['links'].extend(data['links'])
            all_data['headings'].extend(data['headings'])
            all_data['images'].extend(data['images'])
            all_data['text'].extend(data['text'])
            all_data['emails'].extend(data['emails'])
            all_data['phones'].extend(data['phones'])
    
    return all_data


def analyze(aggregated):
    full_text = ' '.join(aggregated['text'])
    words = re.findall(r'\b[a-zA-Z]{4,}\b', full_text.lower())
    stop_words = {'this', 'that', 'with', 'from', 'have', 'will', 'your', 'about', 
                  'which', 'their', 'there', 'would', 'could', 'should', 'been', 'more'}
    filtered = [w for w in words if w not in stop_words]
    word_freq = Counter(filtered).most_common(15)
    
    return {
        'total_words': len(words),
        'unique_words': len(set(words)),
        'top_keywords': word_freq,
        'total_emails': len(set(aggregated['emails'])),
        'total_phones': len(set(aggregated['phones']))
    }


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


def display_results(start_url, results, aggregated, analytics, filename):
    success = len([r for r in results.values() if r['status'] == 'success'])
    failed = len([r for r in results.values() if r['status'] == 'failed'])
    
    print('\n' + '='*80)
    print(f'🌐 FULL SITE CRAWL REPORT: {start_url}')
    print('='*80)
    print(f"📄 PAGES CRAWLED: {success} successful | {failed} failed")
    print(f"📊 AGGREGATE STATISTICS:")
    print(f"  • Total Words: {analytics['total_words']:,} | Unique: {analytics['unique_words']:,}")
    print(f"  • Total Links: {len(aggregated['links']):,} | Unique: {len(set(aggregated['links'])):,}")
    print(f"  • Images: {len(aggregated['images']):,} | Headings: {len(aggregated['headings']):,}")
    print(f"  • Emails: {analytics['total_emails']} | Phones: {analytics['total_phones']}")
    print('-'*80)
    print(f"🔑 TOP KEYWORDS (across all pages):")
    for word, count in analytics['top_keywords'][:8]:
        bar = '█' * min(int(count/10), 40)
        print(f"  {word:<20} {bar} {count}")
    print('-'*80)
    print(f"📋 PAGES BREAKDOWN:")
    for url, data in list(results.items())[:10]:
        status = "✅" if data['status'] == 'success' else "❌"
        if data['status'] == 'success':
            print(f"  {status} {url[:65]}")
            print(f"     Links: {data['links']} | Images: {data['images']} | Text: {data['text_length']} chars")
        else:
            print(f"  {status} {url[:65]} - {data.get('error', 'Unknown error')}")
    if len(results) > 10:
        print(f"  ... and {len(results)-10} more pages")
    print('-'*80)
    print(f"💾 Full report saved: {filename}")
    print('='*80 + '\n')


def main():
    url = input("🌐 Enter starting URL: ").strip()
    if not url.startswith('http'):
        url = 'https://' + url
    
    max_pages = int(input("📄 Max pages to crawl (default 10): ").strip() or "10")
    
    try:
        print(f"\n⏳ Starting crawl from {url}...\n")
        results, visited = crawl_site(url, max_pages=max_pages)
        print(f"\n✅ Crawl complete! Visited {len(visited)} pages.")
        
        aggregated = aggregate_data(results)
        analytics = analyze(aggregated)
        filename = export_full_report(url, results, aggregated, analytics)
        display_results(url, results, aggregated, analytics, filename)
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")


if __name__ == "__main__":
    main()
