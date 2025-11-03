# 🕸️ Web Scraper

A powerful **web scraping and analysis tool** built with **Python + Streamlit + Google Generative AI (Gemini)**.  
It extracts data like links, images, emails, and text from any website, and even generates an **AI-powered summary** of the scraped content.  

---

## 🚀 Features

✅ **Web Scraping** — Extracts:
- Links  
- Headings  
- Emails & Phone Numbers  
- Clean Text Content  

✅ **AI Summarization**
- Summarizes extracted text using **Google Gemini API**  

✅ **Data Visualization**
- Interactive charts using **Plotly**  
- Simple UI built with **Streamlit**

---

## 🧠 Tech Stack

| Layer | Technology |
|--------|-------------|
| **Frontend/UI** | Streamlit |
| **Backend** | Python |
| **Data Handling** | Pandas |
| **Visualization** | Plotly |
| **AI Summarization** | Google Generative AI (Gemini) |
| **Networking** | urllib, re, ssl |
| **HTML Parsing** | HTMLParser |

---

## 📦 Installation

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/your-username/streamlit-ai-webscraper.git
cd streamlit-ai-webscraper
pip install -r requirements.txt (PUT YOUR GEMINI API KEY ON LINE 13, I HAVENT CREATED A VARIABLE FOR IT BECAUSE OF VARIABLE CONSTRAINTS)
streamlit run webScraper.py
