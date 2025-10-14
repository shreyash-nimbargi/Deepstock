# Standard library imports
import json
import logging
import time
from datetime import datetime
import sqlite3
import os

# Third-party imports
import pandas as pd
import numpy as np
import requests
import yfinance as yf
from bs4 import BeautifulSoup
from flask import Flask, request, render_template, make_response, redirect, url_for, session
from fuzzywuzzy import process, fuzz
from werkzeug.security import generate_password_hash, check_password_hash
try:
    from newspaper import Article
except ImportError as e:
    print("Error: Missing required dependencies for newspaper module.")
    print("Please run: pip install 'lxml[html_clean]' newspaper3k")
    raise e
from googlesearch import search

# Initialize Flask app
app = Flask(__name__, template_folder='templates', static_folder='static')

# Configure logging with try-except for file handling
try:
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("stock_app.log"),
            logging.StreamHandler()
        ]
    )
except Exception as e:
    # Fallback to console-only logging if file creation fails
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
logger = logging.getLogger(__name__)

# Set Gemini API key
GEMINI_API_KEY = "AIzaSyDHRR7_kghJOm9P8gDlMn1tJRLgndoN_rQ"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

# Initialize the database
def init_db():
    db_path = os.path.join(os.path.dirname(__file__), 'users.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  email TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL)''')
    conn.commit()
    conn.close()

init_db()

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

def scrape_news(stock_name, stock_symbol):
    stock_name = stock_name.replace("Ltd.", "").strip()  # Clean stock name
    news_text = ""
    stock_short_name = stock_symbol.split('.')[0].lower()  # e.g., "tatapower"
    today_date = datetime.today().strftime("%Y-%m-%d")  # Format: YYYY-MM-DD
    query = f"{stock_name} {stock_short_name} stock {today_date} news"
    
    news_articles = list(search(query, num_results=10, sleep_interval=2))
    
    for i, url in enumerate(news_articles[:10], 1):
        try:
            article = Article(url, fetch_images=False)
            article.download()
            article.parse()
            full_content = article.text.strip()[:1000]  # Limit to 1000 chars

            news_content = f"### news{i} = {article.title} - {full_content}\n"
            news_content.replace("Advertisement Remove Ad","")
            stock_keywords = [stock_name.lower(), stock_short_name]
            
            if any(keyword in article.title.lower() or keyword in full_content.lower() for keyword in stock_keywords):
                if len(news_text.split()) + len(news_content.split()) <= 2000:
                    news_text += news_content
        except:
            pass

    print(news_text)
    
    return news_text if news_text else "No relevant news found."


# Get stock data from Yahoo Finance
def get_stock_data(stock_symbol):
    logger.debug(f"Entering get_stock_data with stock_symbol: {stock_symbol}")
    try:
        stock = yf.Ticker(stock_symbol)
        logger.debug(f"Fetching history for {stock_symbol}")
        hist = stock.history(period="1y")
        logger.debug(f"History data shape: {hist.shape}")
        if hist.empty:
            logger.warning(f"No historical data found for {stock_symbol}")
            return None, None
        volatility = hist['Close'].pct_change().rolling(window=30).std().iloc[-1]
        logger.info(f"Stock data retrieved for {stock_symbol}, volatility: {volatility}")
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
            return {
                "Risk_Level": risk_level,
                "Sentiment_Score": "Neutral",
                "Good_News": [],
                "Bad_News": []
            }
        
        analysis = json.loads(cleaned_text)
        logger.info("Gemini API analysis successful")
        logger.debug(f"Parsed analysis: {analysis}")
        return analysis
    except requests.exceptions.RequestException as e:
        logger.error(f"Gemini API request failed: {str(e)}")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        logger.error(f"Gemini API response parsing failed: {str(e)}")
        risk_level = "Low" if volatility < 0.01 else "Medium" if volatility <= 0.03 else "High"
        return {
            "Risk_Level": risk_level,
            "Sentiment_Score": "Neutral",
            "Good_News": [],
            "Bad_News": []
        }

# Routes
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['email'] = user[1]
            return redirect(url_for('index'))
        
        return render_template("login.html", error="Invalid email or password")
    
    return render_template("login.html", signup=False)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if password != confirm_password:
            return render_template("login.html", signup=True, error="Passwords do not match")

        hashed_password = generate_password_hash(password)
        
        try:
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute("INSERT INTO users (email, password) VALUES (?, ?)", 
                     (email, hashed_password))
            conn.commit()
            conn.close()
            
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template("login.html", signup=True, error="Email already exists")

    return render_template("login.html", signup=True)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route("/", methods=["GET", "POST"])
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    logger.debug("Entering index route")
    logger.info("Received request to root endpoint")
    
    if request.method == "GET":
        logger.info("Rendering initial page (GET request)")
        response = make_response(render_template("index.html", session=session))
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
            response = make_response(render_template("index.html", session=session, error="Stock not found or invalid input."))
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            return response

        news_text = scrape_news(corrected_stock_name, stock_symbol)  # Updated to pass stock_symbol
        hist, volatility = get_stock_data(stock_symbol)
        if hist is None:
            logger.warning("No stock data available")
            response = make_response(render_template("index.html", session=session, error="Stock data not available."))
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            return response

        analysis = analyze_with_gemini(news_text, volatility, corrected_stock_name)
        if not analysis:
            logger.warning("Gemini API analysis returned no result")
            response = make_response(render_template("index.html", session=session, error="Analysis failed."))
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            return response

        risk_level = analysis.get("Risk_Level", "Unknown")
        sentiment = analysis.get("Sentiment_Score", "Unknown")
        good_news = analysis.get("Good_News", [])
        bad_news = analysis.get("Bad_News", [])

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
            session=session,
            stock_name=corrected_stock_name,
            risk_level=risk_level,
            current_price=current_price,
            high_52=high_52,
            low_52=low_52,
            volatility=volatility_display,
            sentiment=sentiment,
            good_news=good_news,
            bad_news=bad_news,
            industry=industry,
            series=series,
            isin=isin
        ))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

# Add session configuration
app.secret_key = 'your-secret-key-here'  # Change this to a secure secret key

if __name__ == "__main__":
    logger.info("Starting DeepStock application")
    app.run(debug=True)