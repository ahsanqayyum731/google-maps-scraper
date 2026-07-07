# Use the official Microsoft Playwright Python image which has python and system dependencies pre-installed
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set the working directory
WORKDIR /app

# Copy requirements.txt first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Set environment variables
ENV PORT=5000
ENV PYTHONUNBUFFERED=1

# Expose port 5000
EXPOSE 5000

# Start the application using Gunicorn.
# Crucial: We use exactly 1 worker because the scraper state is kept in-memory.
# Multiple workers would run in separate processes and wouldn't share the scraping state.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "0", "app:app"]
