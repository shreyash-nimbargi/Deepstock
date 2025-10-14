# DeepStock 📈🧠

A modern stock analysis application using AI to provide insights on Indian stocks with a beautiful, responsive web interface.

---

## 🔥 Features

### Core Functionality
- 🔐 **User Authentication**: Secure login and signup system with SQLite database
- 🔍 **Stock Search**: Search and analyze Indian stocks from NIFTY 500 index
- 🤖 **AI Analysis**: Get risk assessment and sentiment analysis using Google Gemini AI
- 📊 **Real-time Data**: Fetch live stock data from Yahoo Finance API
- 📰 **News Integration**: Scrape and analyze recent news for comprehensive stock insights
- 📱 **Responsive Design**: Modern, mobile-friendly interface with smooth animations

### Frontend Improvements ✨
- **Modular Architecture**: Separated CSS and JavaScript into external files for better maintainability
- **Enhanced UI/UX**: Modern gradient design with improved typography and visual hierarchy
- **Interactive Elements**: Smooth animations, hover effects, and loading states
- **Better Error Handling**: User-friendly error messages and validation feedback
- **Improved Authentication**: Enhanced login/signup forms with real-time validation
- **Stock Table**: Interactive preview table with click-to-select functionality
- **Search Enhancements**: Auto-complete suggestions and input validation

---

## 🛠️ Tech Stack

### Backend
- **Flask**: Web framework for Python
- **SQLite**: Database for user management
- **Google Gemini API**: AI-powered analysis
- **Yahoo Finance API**: Real-time stock data
- **BeautifulSoup**: Web scraping for news

### Frontend
- **HTML5/CSS3**: Modern semantic markup and styling
- **Vanilla JavaScript**: Clean, dependency-free frontend logic
- **Responsive Design**: Mobile-first approach with CSS Grid/Flexbox
- **Google Fonts**: Poppins font family for modern typography

---

## 📁 Project Structure

```
DeepStock/
├── static/
│   ├── style.css              # Main stylesheet with responsive design
│   ├── script.js              # Frontend JavaScript functionality
│   └── ind_nifty500list.csv   # Stock data for preview table
├── templates/
│   ├── index.html             # Main dashboard page
│   └── login.html             # Authentication page
├── main.py                    # Flask application with all routes
├── requirements.txt           # Python dependencies
├── users.db                   # SQLite database (auto-created)
└── README.md                  # This file
```

---

## 🚀 How to Run

1. **Clone the repository:**
```bash
git clone https://github.com/your-username/DeepStock.git
cd DeepStock
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Set up your Gemini API key:**
   - Get your API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Update the `GEMINI_API_KEY` variable in `main.py`

4. **Run the application:**
```bash
python main.py
```

5. **Open your browser:**
   - Navigate to `http://localhost:5000`
   - Create an account or login
   - Start analyzing stocks!

---

## 💡 Usage

### Getting Started
1. **Sign Up/Login**: Create a new account or login with existing credentials
2. **Browse Stocks**: View the preview table of NIFTY 500 stocks
3. **Search & Analyze**: 
   - Type a stock name or symbol in the search bar
   - Click on any stock in the preview table to auto-fill
   - Hit "Analyze" to get AI-powered insights

### Features in Action
- **Risk Assessment**: Get Low/Medium/High risk ratings based on volatility
- **Sentiment Analysis**: Understand market sentiment from recent news
- **Stock Metrics**: View current price, 52-week high/low, and volatility
- **News Summary**: See positive and negative news affecting the stock

---

## 🎨 Frontend Highlights

### Design System
- **Color Palette**: Modern gradients with purple and pink accents
- **Typography**: Poppins font family for clean, readable text
- **Layout**: Card-based design with proper spacing and hierarchy
- **Animations**: Smooth transitions and loading states

### Responsive Features
- **Mobile-First**: Optimized for mobile devices with touch-friendly interactions
- **Adaptive Layout**: Flexible grid system that works on all screen sizes
- **Progressive Enhancement**: Core functionality works without JavaScript

### User Experience
- **Loading States**: Visual feedback during data fetching
- **Error Handling**: Clear error messages with retry options
- **Form Validation**: Real-time validation with visual feedback
- **Accessibility**: Proper ARIA labels and keyboard navigation

---

## 🔧 Configuration

### Environment Variables
```python
# In main.py, update these variables:
GEMINI_API_KEY = "your-gemini-api-key-here"
app.secret_key = 'your-secret-key-here'  # Change for production
```

### Database
- SQLite database is automatically created on first run
- User passwords are securely hashed using Werkzeug
- Session management handles user authentication

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Google Gemini AI** for powerful natural language processing
- **Yahoo Finance** for reliable stock data
- **NIFTY 500** index for comprehensive Indian stock coverage
- **Flask Community** for excellent documentation and support

---

## 📞 Support

If you encounter any issues or have questions:
1. Check the [Issues](https://github.com/your-username/DeepStock/issues) page
2. Create a new issue with detailed information
3. Include screenshots for UI-related problems

---

**Happy Trading! 📈✨**