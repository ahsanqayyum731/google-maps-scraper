# Google Maps Business Scraper

A web-based Google Maps scraper built with **Python**, **Flask**, and **Playwright**. It automates the discovery and details extraction of business listings (leads) on Google Maps for a given search query (category and location), then lets you download the results as Excel (`.xlsx`) or CSV files.

## Features

- **Search by Category & Location**: Target specific business types in any city/region.
- **Scroll & Auto-Discover**: Automatically scrolls the Google Maps list panel to load listings.
- **Extracts Rich Lead Data**:
  - Business Name
  - Rating & Review Count
  - Category
  - Address
  - Phone Number
  - Website URL
  - Google Maps Link
- **Download Options**: Export findings directly to formatted Excel spreadsheets (`.xlsx`) or CSV files.
- **Real-time UI**: A clean dashboard showing progress, live logs, and scraped results.

## Project Structure

```
├── static/
│   ├── main.js        # Frontend interface logic
│   └── style.css      # CSS styling for the dashboard
├── templates/
│   └── index.html     # HTML structure of the dashboard
├── app.py             # Flask Web Server & API routes
├── scraper.py         # Playwright scraping logic
└── .gitignore         # Ignores virtual env and temporary caches
```

## Getting Started

### Prerequisites

- Python 3.8+
- Google Chrome or Chromium (managed by Playwright)

### Installation

1. **Clone the repository** (after uploading to your GitHub):
   ```bash
   git clone <your-repository-url>
   cd google-scrapper
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv .venv
   ```

3. **Activate the virtual environment**:
   - **Windows (PowerShell)**:
     ```powershell
     .venv\Scripts\Activate.ps1
     ```
   - **Windows (CMD)**:
     ```cmd
     .venv\Scripts\activate.bat
     ```
   - **macOS/Linux**:
     ```bash
     source .venv/bin/activate
     ```

4. **Install dependencies**:
   ```bash
   pip install flask pandas playwright openpyxl
   ```

5. **Install Playwright Browsers**:
   ```bash
   playwright install chromium
   ```

### Running the Scraper

1. Start the Flask application:
   ```bash
   python app.py
   ```
2. Open your browser and navigate to `http://127.0.0.1:5000`.
3. Enter your target business category and location, specify a limit, and click **Start Scraping**.
