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
        logger.debug(f"Stock list sample: {dict(list(nse_stocks.items())[:5])}")
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
        logger.info(f"Using fallback NSE stocks: {len(nse_stocks)} stocks")
        logger.debug(f"Fallback stock list: {nse_stocks}")
        return nse_stocks

# Fuzzy match stock name using Company Name, fallback to Symbol
def fuzzy_match_stock(stock_name, stock_list):
    logger.debug(f"Entering fuzzy_match_stock with stock_name: {stock_name}")
    company_names = list(stock_list.keys())
    symbols = [details['Symbol'].split('.')[0] for details in stock_list.values()]  # e.g., "RELIANCE", "TCS"
    
    # First try matching with company name
    logger.debug(f"Available company names: {company_names[:5]}... (total {len(company_names)})")
    best_match, score = process.extractOne(stock_name, company_names, scorer=fuzz.token_sort_ratio)
    logger.info(f"Best match by name: {best_match} with score: {score}")
    
    if score > 50:
        matched_details = stock_list[best_match]
        logger.debug(f"Matched details by name: {matched_details}")
        logger.info(f"Corrected company name: {best_match}")
        return matched_details['Symbol'], best_match, matched_details
    
    # Fallback to symbol matching
    logger.debug(f"No good name match, trying symbols: {symbols[:5]}... (total {len(symbols)})")
    best_symbol_match, symbol_score = process.extractOne(stock_name, symbols, scorer=fuzz.token_sort_ratio)
    logger.info(f"Best match by symbol: {best_symbol_match} with score: {symbol_score}")
    
    if symbol_score > 50:
        for company, details in stock_list.items():
            if details['Symbol'].split('.')[0] == best_symbol_match:
                logger.debug(f"Matched details by symbol: {details}")
                logger.info(f"Corrected company name by symbol: {company}")
                return details['Symbol'], company, details
    
    logger.warning(f"No good match found for {stock_name} (name score: {score}, symbol score: {symbol_score})")
    return None, None, None

    try:
        # Normalize symbol (ensure exchange suffix present)
        symbol = stock_symbol
        if '.' not in symbol:
            symbol = f"{symbol}.NS"

        # Try multiple strategies to get history (some tickers / yfinance endpoints can be flaky)
        logger.debug(f"Fetching history for normalized symbol: {symbol}")

        # 1) Try Ticker.history (simple and fast)
        stock = yf.Ticker(symbol)
        hist = None
        try:
            hist = stock.history(period="1y", interval="1d", auto_adjust=False)
            logger.debug(f"Ticker.history shape: {getattr(hist, 'shape', None)}")
        except Exception as e:
            logger.debug(f"Ticker.history attempt failed for {symbol}: {e}")

        # 2) If empty, try yf.download which sometimes returns results when history() does not
        if hist is None or (hasattr(hist, 'empty') and hist.empty) or len(hist) == 0:
            logger.debug(f"Ticker.history empty for {symbol}, trying yf.download(period=1y)")
            try:
                hist = yf.download(symbol, period="1y", interval="1d", progress=False, threads=False)
                logger.debug(f"yf.download (1y) shape: {getattr(hist, 'shape', None)}")
            except Exception as e:
                logger.debug(f"yf.download (1y) failed for {symbol}: {e}")

        # 3) Try longer period
        if hist is None or (hasattr(hist, 'empty') and hist.empty) or len(hist) == 0:
            logger.debug(f"yf.download returned nothing, trying yf.download(period=5y) for {symbol}")
            try:
                hist = yf.download(symbol, period="5y", interval="1d", progress=False, threads=False)
                logger.debug(f"yf.download (5y) shape: {getattr(hist, 'shape', None)}")
            except Exception as e:
                logger.debug(f"yf.download (5y) failed for {symbol}: {e}")

        # 4) Fallback: try without exchange suffix (some tickers are indexed differently)
        if hist is None or (hasattr(hist, 'empty') and hist.empty) or len(hist) == 0:
            base = symbol.split('.')[0]
            logger.debug(f"All attempts empty, trying base symbol {base}")
            try:
                stock2 = yf.Ticker(base)
                hist = stock2.history(period="1y", interval="1d", auto_adjust=False)
                logger.debug(f"Base ticker.history shape: {getattr(hist, 'shape', None)}")
            except Exception as e:
                logger.debug(f"Base ticker.history attempt failed for {base}: {e}")

        # If result is a multi-index DataFrame (download with multiple tickers), try to normalize
        if hist is not None and hasattr(hist, 'columns') and getattr(hist.columns, 'nlevels', 1) > 1:
            logger.debug("History has MultiIndex columns; attempting to normalize to single-column index")
            try:
                # Prefer selecting the symbol group if present
                if symbol in hist.columns.levels[0]:
                    hist = hist[symbol]
                else:
                    # Flatten to second level names (Open/Close/High/Low/Volume)
                    hist.columns = hist.columns.get_level_values(-1)
            except Exception as e:
                logger.debug(f"Failed to normalize MultiIndex columns: {e}")

        if hist is None or (hasattr(hist, 'empty') and hist.empty) or len(hist) == 0:
            logger.warning(f"No historical data found for {stock_symbol}")
            return None, None

        # Ensure 'Close' column exists
        if 'Close' not in hist.columns and 'close' in hist.columns:
            hist.rename(columns={c: c.capitalize() for c in hist.columns}, inplace=True)

        # Compute volatility using Close price (guard if not present)
        if 'Close' in hist.columns:
            volatility = hist['Close'].pct_change().rolling(window=30).std().iloc[-1]
        else:
            logger.warning(f"'Close' column missing in history for {symbol}; cannot compute volatility")
            volatility = float('nan')

        logger.info(f"Stock data retrieved for {symbol}, volatility: {volatility}")
        if 'Close' in hist.columns:
            logger.debug(f"Latest close price: {hist['Close'].iloc[-1]}")
            logger.debug(f"52-week high: {hist['Close'].max()}, low: {hist['Close'].min()}")
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
    
    logger.info("Sending request to Gemini API for analysis")
    logger.debug(f"Request URL: {url}")
    logger.debug(f"Request headers: {headers}")
    logger.debug(f"Request payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        logger.debug(f"Response status code: {response.status_code}")
        logger.debug(f"Response headers: {response.headers}")
        logger.debug(f"Raw response text: {response.text}")
        response.raise_for_status()
        result = response.json()
        logger.debug(f"Parsed JSON response: {json.dumps(result, indent=2)}")
        generated_text = result["candidates"][0]["content"]["parts"][0]["text"]
        logger.info(f"Generated text from Gemini: {generated_text}")
        
        cleaned_text = generated_text.strip()
        if cleaned_text.startswith("```json") and cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[7:-3].strip()
            logger.debug(f"Cleaned text after removing Markdown: {cleaned_text}")
        elif cleaned_text.startswith("```") and cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[3:-3].strip()
            logger.debug(f"Cleaned text after removing generic Markdown: {cleaned_text}")
        
        if not cleaned_text:
            logger.warning("Gemini returned an empty response after cleaning")
            risk_level = "Low" if volatility < 0.01 else "Medium" if volatility <= 0.03 else "High"
            fallback = {
                "Risk_Level": risk_level,
                "Sentiment_Score": "Neutral",
                "Good_News": [],
                "Bad_News": []
            }
            return fallback, "fallback"

        analysis = json.loads(cleaned_text)
        logger.info("Gemini API analysis successful")
        logger.debug(f"Parsed analysis: {analysis}")
        return analysis, "gemini"
    except requests.exceptions.RequestException as e:
        # On request-level errors (network, 4xx/5xx from API), log and return a safe fallback
        logger.error(f"Gemini API request failed: {str(e)}")
        risk_level = "Low" if volatility < 0.01 else "Medium" if volatility <= 0.03 else "High"
        fallback = {
            "Risk_Level": risk_level,
            "Sentiment_Score": "Neutral",
            "Good_News": [],
            "Bad_News": []
        }
        return fallback, "fallback"
    except (KeyError, json.JSONDecodeError) as e:
        logger.error(f"Gemini API response parsing failed: {str(e)}")
        risk_level = "Low" if volatility < 0.01 else "Medium" if volatility <= 0.03 else "High"
        fallback = {
            "Risk_Level": risk_level,
            "Sentiment_Score": "Neutral",
            "Good_News": [],
            "Bad_News": []
        }
        return fallback, "fallback"


# Simple heuristic classifier to split scraped news into good and bad lists
def classify_news_from_text(news_text, stock_name, max_items=5):
    """Return (good_news, bad_news) lists using simple sentiment heuristics.

    - Splits news_text by lines that start with '###' (as produced by scrape_news).
    - Uses TextBlob polarity to classify sentiment per item.
    - Filters for items that mention the stock_name (case-insensitive).
    """
    logger.debug("Entering classify_news_from_text")
    lines = [ln.strip() for ln in news_text.split('\n') if ln.strip()]
    candidates = []
    stock_lower = stock_name.lower()
    # simple keyword lists for heuristic scoring
    good_keywords = ['profit', 'growth', 'gain', 'beat', 'rise', 'increase', 'upgrade', 'acqui', 'contract', 'deal', 'win', 'expansion', 'record', 'surge', 'revenue']
    bad_keywords = ['loss', 'fall', 'drop', 'decline', 'downgrade', 'miss', 'fraud', 'scam', 'lawsuit', 'arrest', 'investigation', 'slump', 'cut', 'warn', 'weak', 'debt']

    for ln in lines:
        # Expecting lines like: ### news1 = Title - content
        if ln.startswith('###') and '=' in ln:
            try:
                _, rest = ln.split('=', 1)
                title_body = rest.strip()
            except:
                title_body = ln
        else:
            title_body = ln

        # check relevance
        if stock_lower in title_body.lower() or stock_lower.split()[0] in title_body.lower():
            # short preview
            preview = title_body
            # sentiment
            # heuristic polarity: count keyword matches
            lowered = preview.lower()
            pos_score = sum(1 for kw in good_keywords if kw in lowered)
            neg_score = sum(1 for kw in bad_keywords if kw in lowered)
            polarity = pos_score - neg_score
            candidates.append((preview, polarity))

    # sort by polarity for good and bad
    good = [c[0] for c in sorted(candidates, key=lambda x: -x[1])[:max_items] if c[1] > 0]
    bad = [c[0] for c in sorted(candidates, key=lambda x: x[1])[:max_items] if c[1] < 0]

    logger.info(f"Classified news into {len(good)} good and {len(bad)} bad items")
    return good, bad

# Routes
@app.route("/", methods=["GET", "POST"])
def index():
    logger.debug("Entering index route")
    logger.info("Received request to root endpoint")
    
    if request.method == "GET":
        logger.info("Rendering initial page (GET request)")
        response = make_response(render_template("index.html"))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    
    if request.method == "POST":
        stock_name = request.form.get("stock_name")
        logger.info(f"Processing stock name: {stock_name}")
        logger.debug(f"Form data: {request.form}")
        
        nse_stocks = get_nse_stocks()
        stock_symbol, corrected_stock_name, stock_details = fuzzy_match_stock(stock_name, nse_stocks)
        if not stock_symbol:
            logger.warning("Stock symbol not found after fuzzy matching")
            response = make_response(render_template("index.html", error="Stock not found or invalid input."))
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            return response

        news_text = scrape_news(corrected_stock_name, stock_symbol)  # Updated to pass stock_symbol
        hist, volatility = get_stock_data(stock_symbol)
        if hist is None:
            logger.warning("No stock data available")
            response = make_response(render_template("index.html", error="Stock data not available."))
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            return response

        analysis, analysis_source = analyze_with_gemini(news_text, volatility, corrected_stock_name)
        # Ensure analysis is a dict
        if not analysis:
            logger.warning("Gemini API analysis returned no result")
            response = make_response(render_template("index.html", error="Analysis failed."))
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            return response

        # Coerce fields into expected types and fallback to heuristic classification if empty
        risk_level = analysis.get("Risk_Level", "Unknown") if isinstance(analysis, dict) else "Unknown"
        sentiment = analysis.get("Sentiment_Score", "Unknown") if isinstance(analysis, dict) else "Unknown"
        good_news = analysis.get("Good_News", []) if isinstance(analysis, dict) else []
        bad_news = analysis.get("Bad_News", []) if isinstance(analysis, dict) else []

        # If Gemini returned empty lists for news, use heuristic classifier on scraped news
        try:
            if (not good_news) and (not bad_news) and news_text and "No relevant news" not in news_text:
                logger.info("Gemini returned no news items; running heuristic classifier on scraped news")
                hg, hb = classify_news_from_text(news_text, corrected_stock_name, max_items=6)
                # Only use classifier results if it found something
                if hg or hb:
                    good_news = hg if hg else good_news
                    bad_news = hb if hb else bad_news
                    # Update sentiment based on counts
                    if len(hg) > len(hb):
                        sentiment = "Positive"
                    elif len(hb) > len(hg):
                        sentiment = "Negative"
                    else:
                        sentiment = "Neutral"
        except Exception as e:
            logger.error(f"Heuristic classification failed: {e}")

        current_price = f"{hist['Close'].iloc[-1]:.2f}"
        high_52 = f"{hist['Close'].max():.2f}"
        low_52 = f"{hist['Close'].min():.2f}"
        volatility_display = f"{volatility:.4f}"
        industry = stock_details['Industry']
        series = stock_details['Series']
        isin = stock_details['ISIN']

        logger.info(f"Rendering results for {corrected_stock_name}: Risk={risk_level}, Sentiment={sentiment}")
        logger.debug(f"Results data: risk_level={risk_level}, sentiment={sentiment}, good_news={good_news}, bad_news={bad_news}")
        logger.debug(f"Stock metrics: current_price={current_price}, high_52={high_52}, low_52={low_52}, volatility={volatility_display}")
        logger.debug(f"Additional stock info: industry={industry}, series={series}, isin={isin}")

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
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

if __name__ == "__main__":
    logger.info("Starting DeepStock application")
    app.run(debug=True)