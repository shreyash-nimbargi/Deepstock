from flask import Flask, request, render_template, make_response
import yfinance as yf
import requests
import pandas as pd
import numpy as np
import json
from fuzzywuzzy import process, fuzz
import logging
import os
from dotenv import load_dotenv
import sys
from googlesearch import search
from newspaper import Article
from datetime import datetime

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__, template_folder='templates')

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("stock_app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Set Gemini API key from environment variable
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
# Allow configuring model via env var; default to gemini-1.5-flash
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/{GEMINI_MODEL}:generateContent"

# Load NSE stocks from CSV
def get_nse_stocks():
    logger.debug("Entering get_nse_stocks function")
    try:
        df = pd.read_csv("ind_nifty500list.csv")
        nse_stocks = {
            row['Company Name']: {
                'Symbol': f"{row['Symbol']}.NS",
                'Industry': row['Industry'],
                'Series': row['Series'],
                'ISIN': row['ISIN Code']
            } for _, row in df.iterrows()
        }
        logger.info(f"NSE stocks loaded from CSV: {len(nse_stocks)} stocks")
        return nse_stocks
    except Exception as e:
        logger.error(f"Error loading NSE stocks from CSV: {str(e)}")
        nse_stocks = {
            "Reliance Industries Limited": {
                'Symbol': "RELIANCE.NS",
                'Industry': "Oil & Gas",
                'Series': "EQ",
                'ISIN': "INE002A01018"
            },
            "Tata Consultancy Services Limited": {
                'Symbol': "TCS.NS",
                'Industry': "IT Services",
                'Series': "EQ",
                'ISIN': "INE467B01029"
            }
        }
        return nse_stocks

# Fuzzy match stock name using Company Name, fallback to Symbol
def fuzzy_match_stock(stock_name, stock_list):
    logger.debug(f"Entering fuzzy_match_stock with stock_name: {stock_name}")
    company_names = list(stock_list.keys())
    symbols = [details['Symbol'].split('.')[0] for details in stock_list.values()]
    
    # First try matching with company name
    best_match, score = process.extractOne(stock_name, company_names, scorer=fuzz.token_sort_ratio)
    logger.info(f"Best match by name: {best_match} with score: {score}")
    
    if score > 50:
        matched_details = stock_list[best_match]
        return matched_details['Symbol'], best_match, matched_details
    
    # Fallback to symbol matching
    best_symbol_match, symbol_score = process.extractOne(stock_name, symbols, scorer=fuzz.token_sort_ratio)
    logger.info(f"Best match by symbol: {best_symbol_match} with score: {symbol_score}")
    
    if symbol_score > 50:
        for company, details in stock_list.items():
            if details['Symbol'].split('.')[0] == best_symbol_match:
                return details['Symbol'], company, details
    
    return None, None, None

def scrape_news(stock_name, stock_symbol):
    stock_name = stock_name.replace("Ltd.", "").strip()  # Clean stock name
    news_text = ""
    stock_short_name = stock_symbol.split('.')[0].lower()  # e.g., "tatapower"
    query = f"{stock_name} {stock_short_name} stock news"
    
    logger.info(f"Scraping news for {stock_name} with query: {query}")

    try:
        # googlesearch-python uses num_results, not stop/num
        # We use advanced=True to get title/description if possible, but fallback to strings
        try:
            results_gen = search(query, num_results=10, advanced=True)
            news_articles = list(results_gen)
        except TypeError:
            # Fallback for other versions of googlesearch
            logger.warning("googlesearch advanced=True failed, trying standard search")
            results_gen = search(query, num=10, stop=10)
            news_articles = list(results_gen)

        urls = []
        for item in news_articles:
            if isinstance(item, str):
                urls.append(item)
            elif hasattr(item, 'url'):
                urls.append(item.url)
        
        urls = urls[:8] # Limit to 8
        logger.info(f"Found {len(urls)} news URLs: {urls}")
        
        for i, url in enumerate(urls, 1):
            try:
                article = Article(url, fetch_images=False)
                article.download()
                article.parse()
                full_content = article.text.strip()[:1000]  # Limit to 1000 chars

                news_content = f"### news{i} = {article.title} - {full_content}\n"
                news_content = news_content.replace("Advertisement Remove Ad","")
                
                # looser keyword matching
                stock_keywords = [stock_name.lower(), stock_short_name, "stock", "market", "share", "price", "trade"]
                
                if any(keyword in article.title.lower() or keyword in full_content.lower() for keyword in stock_keywords):
                    if len(news_text.split()) + len(news_content.split()) <= 3000: # Increased limit
                        news_text += news_content
            except Exception as e:
                logger.debug(f"Failed to parse article {url}: {e}")
                pass

        logger.info(f"Scraped news length: {len(news_text)} chars")
        
        return news_text if news_text else "No relevant news found."
    except Exception as e:
        logger.error(f"Error in scrape_news: {e}")
        return "No relevant news found."

# Get stock data from Yahoo Finance
def get_stock_data(stock_symbol):
    logger.debug(f"Entering get_stock_data with stock_symbol: {stock_symbol}")
    try:
        # Normalize symbol (ensure exchange suffix present)
        symbol = stock_symbol
        if '.' not in symbol:
            symbol = f"{symbol}.NS"

        logger.debug(f"Fetching history for normalized symbol: {symbol}")

        # 1) Try Ticker.history (simple and fast)
        stock = yf.Ticker(symbol)
        hist = None
        try:
            hist = stock.history(period="1y", interval="1d", auto_adjust=False)
        except Exception as e:
            logger.debug(f"Ticker.history attempt failed for {symbol}: {e}")

        # 2) If empty, try yf.download
        if hist is None or (hasattr(hist, 'empty') and hist.empty) or len(hist) == 0:
            try:
                hist = yf.download(symbol, period="1y", interval="1d", progress=False, threads=False)
            except Exception as e:
                logger.debug(f"yf.download (1y) failed for {symbol}: {e}")

        # 3) Try longer period
        if hist is None or (hasattr(hist, 'empty') and hist.empty) or len(hist) == 0:
            try:
                hist = yf.download(symbol, period="5y", interval="1d", progress=False, threads=False)
            except Exception as e:
                logger.debug(f"yf.download (5y) failed for {symbol}: {e}")

        # 4) Fallback: try without exchange suffix
        if hist is None or (hasattr(hist, 'empty') and hist.empty) or len(hist) == 0:
            base = symbol.split('.')[0]
            try:
                stock2 = yf.Ticker(base)
                hist = stock2.history(period="1y", interval="1d", auto_adjust=False)
            except Exception as e:
                logger.debug(f"Base ticker.history attempt failed for {base}: {e}")

        # Normalize MultiIndex columns
        if hist is not None and hasattr(hist, 'columns') and getattr(hist.columns, 'nlevels', 1) > 1:
            try:
                if symbol in hist.columns.levels[0]:
                    hist = hist[symbol]
                else:
                    hist.columns = hist.columns.get_level_values(-1)
            except Exception as e:
                logger.debug(f"Failed to normalize MultiIndex columns: {e}")

        if hist is None or (hasattr(hist, 'empty') and hist.empty) or len(hist) == 0:
            logger.warning(f"No historical data found for {stock_symbol}")
            return None, None

        # Ensure 'Close' column exists
        if 'Close' not in hist.columns and 'close' in hist.columns:
            hist.rename(columns={c: c.capitalize() for c in hist.columns}, inplace=True)

        # Compute volatility using Close price
        if 'Close' in hist.columns:
            volatility = hist['Close'].pct_change().rolling(window=30).std().iloc[-1]
        else:
            logger.warning(f"'Close' column missing in history for {symbol}; cannot compute volatility")
            volatility = float('nan')

        logger.info(f"Stock data retrieved for {symbol}, volatility: {volatility}")
        return hist, volatility
    except Exception as e:
        logger.error(f"Stock data retrieval failed for {stock_symbol}: {str(e)}")
        return None, None

# Analyze with Gemini API
def analyze_with_gemini(news_text, volatility, stock_name):
    logger.debug("Entering analyze_with_gemini")
    prompt = f"""
    Analyze the following news and volatility data for the stock '{stock_name}'. Return a JSON object with:
    - Risk_Level: High/Medium/Low (based on volatility: low < 0.01, medium 0.01-0.03, high > 0.03)
    - Sentiment_Score: Positive/Neutral/Negative (based on news sentiment analysis, only considering news relevant to {stock_name})
    - Good_News: List of positive news upto 20 words each specifically about {stock_name}
    - Bad_News: List of negative news upto 20 words each specifically about {stock_name}

    Ignore news items that are not explicitly related to {stock_name}.

    Volatility: {volatility}

    News:
    {news_text}

    Return the output strictly as a JSON object.
    """
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        generated_text = result["candidates"][0]["content"]["parts"][0]["text"]
        logger.info(f"Generated text from Gemini: {generated_text}")
        
        cleaned_text = generated_text.strip()
        if cleaned_text.startswith("```json") and cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[7:-3].strip()
        elif cleaned_text.startswith("```") and cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[3:-3].strip()
        
        if not cleaned_text:
            logger.warning("Gemini returned an empty response after cleaning")
            return None, "fallback"

        analysis = json.loads(cleaned_text)
        return analysis, "gemini"
    except Exception as e:
        logger.error(f"Gemini API request failed: {str(e)}")
        return None, "fallback"

# Simple heuristic classifier to split scraped news into good and bad lists
def classify_news_from_text(news_text, stock_name, max_items=5):
    lines = [ln.strip() for ln in news_text.split('\n') if ln.strip()]
    candidates = []
    stock_lower = stock_name.lower()
    good_keywords = ['profit', 'growth', 'gain', 'beat', 'rise', 'increase', 'upgrade', 'acqui', 'contract', 'deal', 'win', 'expansion', 'record', 'surge', 'revenue']
    bad_keywords = ['loss', 'fall', 'drop', 'decline', 'downgrade', 'miss', 'fraud', 'scam', 'lawsuit', 'arrest', 'investigation', 'slump', 'cut', 'warn', 'weak', 'debt']

    for ln in lines:
        if ln.startswith('###') and '=' in ln:
            try:
                _, rest = ln.split('=', 1)
                title_body = rest.strip()
            except:
                title_body = ln
        else:
            title_body = ln

        if stock_lower in title_body.lower() or stock_lower.split()[0] in title_body.lower():
            preview = title_body
            lowered = preview.lower()
            pos_score = sum(1 for kw in good_keywords if kw in lowered)
            neg_score = sum(1 for kw in bad_keywords if kw in lowered)
            polarity = pos_score - neg_score
            candidates.append((preview, polarity))

    good = [c[0] for c in sorted(candidates, key=lambda x: -x[1])[:max_items] if c[1] > 0]
    bad = [c[0] for c in sorted(candidates, key=lambda x: x[1])[:max_items] if c[1] < 0]
    return good, bad

# Routes
@app.route("/", methods=["GET", "POST"])
def index():
    logger.debug("Entering index route")
    
    if request.method == "GET":
        response = make_response(render_template("index.html"))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response
    
    if request.method == "POST":
        stock_name = request.form.get("stock_name")
        logger.info(f"Processing stock name: {stock_name}")
        
        nse_stocks = get_nse_stocks()
        stock_symbol, corrected_stock_name, stock_details = fuzzy_match_stock(stock_name, nse_stocks)
        if not stock_symbol:
            response = make_response(render_template("index.html", error="Stock not found or invalid input."))
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            return response

        news_text = scrape_news(corrected_stock_name, stock_symbol)
        hist, volatility = get_stock_data(stock_symbol)
        if hist is None:
            response = make_response(render_template("index.html", error="Stock data not available."))
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            return response

        analysis, analysis_source = analyze_with_gemini(news_text, volatility, corrected_stock_name)
        
        # Default values
        risk_level = "Unknown"
        sentiment = "Unknown"
        good_news = []
        bad_news = []

        if analysis:
            risk_level = analysis.get("Risk_Level", "Unknown")
            sentiment = analysis.get("Sentiment_Score", "Unknown")
            good_news = analysis.get("Good_News", [])
            bad_news = analysis.get("Bad_News", [])
        else:
            # Fallback logic
            risk_level = "Low" if volatility < 0.01 else "Medium" if volatility <= 0.03 else "High"
            sentiment = "Neutral"

        # Heuristic fallback for news
        if (not good_news) and (not bad_news) and news_text and "No relevant news" not in news_text:
            hg, hb = classify_news_from_text(news_text, corrected_stock_name, max_items=6)
            if hg or hb:
                good_news = hg if hg else good_news
                bad_news = hb if hb else bad_news
                if len(hg) > len(hb):
                    sentiment = "Positive"
                elif len(hb) > len(hg):
                    sentiment = "Negative"

        current_price = f"{hist['Close'].iloc[-1]:.2f}"
        high_52 = f"{hist['Close'].max():.2f}"
        low_52 = f"{hist['Close'].min():.2f}"
        volatility_display = f"{volatility:.4f}"
        industry = stock_details['Industry']
        series = stock_details['Series']
        isin = stock_details['ISIN']

        response = make_response(render_template(
            "index.html",
            stock_name=corrected_stock_name,
            risk_level=risk_level,
            current_price=current_price,
            high_52=high_52,
            low_52=low_52,
            volatility=volatility_display,
            sentiment=sentiment,
            good_news=good_news,
            bad_news=bad_news,
            analysis_source=analysis_source,
            industry=industry,
            series=series,
            isin=isin
        ))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response

if __name__ == "__main__":
    logger.info("Starting DeepStock application")
    app.run(debug=True, use_reloader=False)