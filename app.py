import io
import threading
from flask import Flask, request, jsonify, render_template, send_file
import pandas as pd
from scraper import scraper_state, state_lock, run_scraper, set_status

app = Flask(__name__)

# Route to serve the UI
@app.route("/")
def index():
    return render_template("index.html")

# Route to start scraping
@app.route("/api/scrape", methods=["POST"])
def start_scrape():
    global scraper_state
    
    data = request.json or {}
    category = data.get("category", "").strip()
    location = data.get("location", "").strip()
    limit = data.get("limit", 20)
    headless = data.get("headless", True)
    
    if not category:
        return jsonify({"error": "Category is required."}), 400
    if not location:
        return jsonify({"error": "Location is required."}), 400
        
    try:
        limit = int(limit)
        if limit <= 0:
            limit = 20
    except ValueError:
        limit = 20
        
    with state_lock:
        if scraper_state["status"] == "running":
            return jsonify({"error": "A scraping task is already running."}), 400
            
    # Start the scraper in a background thread
    t = threading.Thread(
        target=run_scraper,
        args=(category, location, limit, headless),
        daemon=True
    )
    t.start()
    
    return jsonify({"message": "Scraping started successfully."})

# Route to get current scraper status and results
@app.route("/api/status", methods=["GET"])
def get_status():
    with state_lock:
        # Create a copy of the state to avoid thread race conditions
        state_copy = {
            "status": scraper_state["status"],
            "progress": scraper_state["progress"],
            "message": scraper_state["message"],
            "total_found": scraper_state["total_found"],
            "scraped_count": scraper_state["scraped_count"],
            "logs": scraper_state["logs"][-30:], # send last 30 logs to avoid large payload
            "results": scraper_state["results"] # Send all scraped items
        }
    return jsonify(state_copy)

# Route to stop current scraper
@app.route("/api/stop", methods=["POST"])
def stop_scrape():
    with state_lock:
        if scraper_state["status"] == "running":
            scraper_state["status"] = "stopping"
            scraper_state["message"] = "Stopping scraper..."
            return jsonify({"message": "Stop signal sent to scraper."})
        else:
            return jsonify({"error": "Scraper is not running."}), 400

# Route to download results as Excel or CSV
@app.route("/api/download/<file_format>", methods=["GET"])
def download_results(file_format):
    with state_lock:
        results = list(scraper_state["results"])
        query = scraper_state["current_query"] or "leads"
        location = scraper_state["current_location"] or "google_maps"
        
    if not results:
        return "No results available to download.", 400
        
    # Create DataFrame
    df = pd.DataFrame(results)
    
    # Reorder and rename columns
    columns_mapping = {
        "name": "Business Name",
        "category": "Category",
        "rating": "Rating",
        "reviews_count": "Reviews Count",
        "phone": "Phone Number",
        "website": "Website",
        "address": "Address",
        "maps_url": "Google Maps Link"
    }
    
    # Filter to only keep known columns and rename them
    df = df[[col for col in columns_mapping.keys() if col in df.columns]]
    df.rename(columns=columns_mapping, inplace=True)
    
    # Sanitize query and location for filename
    safe_query = "".join(c for c in query if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
    safe_location = "".join(c for c in location if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
    filename = f"gmaps_{safe_query}_{safe_location}"
    
    if file_format == "xlsx":
        output = io.BytesIO()
        try:
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Google Maps Leads')
                
                # Auto-adjust column widths for better Excel format
                worksheet = writer.sheets['Google Maps Leads']
                for col in worksheet.columns:
                    max_len = max(len(str(cell.value or '')) for cell in col)
                    col_letter = col[0].column_letter
                    worksheet.column_dimensions[col_letter].width = max(max_len + 3, 10)
                    
            output.seek(0)
            return send_file(
                output,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=f"{filename}.xlsx"
            )
        except Exception as e:
            return f"Error generating Excel file: {str(e)}", 500
            
    elif file_format == "csv":
        output = io.BytesIO()
        try:
            # Excel-friendly CSV encoding (UTF-8 with BOM)
            df.to_csv(output, index=False, encoding='utf-8-sig')
            output.seek(0)
            return send_file(
                output,
                mimetype="text/csv",
                as_attachment=True,
                download_name=f"{filename}.csv"
            )
        except Exception as e:
            return f"Error generating CSV file: {str(e)}", 500
            
    else:
        return "Invalid file format. Use 'xlsx' or 'csv'.", 400

if __name__ == "__main__":
    # Run server locally on port 5000
    app.run(host="127.0.0.1", port=5000, debug=True)
