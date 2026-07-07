// UI Elements
const scrapeForm = document.getElementById('scrape-form');
const categoryInput = document.getElementById('category');
const locationInput = document.getElementById('location');
const limitInput = document.getElementById('limit');
const headlessCheckbox = document.getElementById('headless');
const startBtn = document.getElementById('start-btn');
const stopBtn = document.getElementById('stop-btn');

// Stats Elements
const statDiscovered = document.getElementById('stat-discovered');
const statScraped = document.getElementById('stat-scraped');
const statAvgRating = document.getElementById('stat-avg-rating');
const statSuccessRate = document.getElementById('stat-success-rate');

// Progress Elements
const statusBadge = document.getElementById('status-badge');
const statusMsg = document.getElementById('status-msg');
const progressPercent = document.getElementById('progress-percent');
const progressBarFill = document.getElementById('progress-bar-fill');

// Logs & Table Elements
const consoleLogs = document.getElementById('console-logs');
const clearLogsBtn = document.getElementById('clear-logs-btn');
const tableBody = document.getElementById('table-body');
const downloadXlsxBtn = document.getElementById('download-xlsx');
const downloadCsvBtn = document.getElementById('download-csv');

// State Variables
let pollingInterval = null;
let localLogs = [];
let scrapedLeads = [];

// Helper: Append a single log to the console
function appendLog(logText) {
    const logLine = document.createElement('div');
    logLine.className = 'log-line';
    
    // Color system logs
    if (logText.includes('[System]')) {
        logLine.classList.add('text-muted');
    } else if (logText.toLowerCase().includes('error') || logText.toLowerCase().includes('failed')) {
        logLine.style.color = '#ef4444'; // Red
    } else if (logText.toLowerCase().includes('completed') || logText.toLowerCase().includes('success')) {
        logLine.style.color = '#10b981'; // Green
    } else if (logText.toLowerCase().includes('scraped')) {
        logLine.style.color = '#06b6d4'; // Cyan
    }
    
    logLine.textContent = logText;
    consoleLogs.appendChild(logLine);
    consoleLogs.scrollTop = consoleLogs.scrollHeight;
}

// Clear Logs
clearLogsBtn.addEventListener('click', () => {
    consoleLogs.innerHTML = '';
    localLogs = [];
    appendLog('[System] Console log cleared.');
});

// Start Scraping
scrapeForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const category = categoryInput.value.trim();
    const location = locationInput.value.trim();
    const limit = parseInt(limitInput.value) || 20;
    const headless = headlessCheckbox.checked;
    
    if (!category || !location) return;
    
    // Reset state & UI
    localLogs = [];
    scrapedLeads = [];
    consoleLogs.innerHTML = '';
    tableBody.innerHTML = `
        <tr class="empty-row">
            <td colspan="9">
                <div class="empty-state">
                    <i class="fa-solid fa-spinner fa-spin empty-icon"></i>
                    <p>Initializing scraper. Please wait...</p>
                </div>
            </td>
        </tr>
    `;
    
    appendLog(`[System] Initializing scraper request for "${category}" in "${location}"...`);
    
    // Toggle buttons
    startBtn.disabled = true;
    startBtn.classList.add('disabled');
    stopBtn.disabled = false;
    stopBtn.classList.remove('disabled');
    
    // Disable download buttons
    downloadXlsxBtn.disabled = true;
    downloadXlsxBtn.classList.add('disabled');
    downloadCsvBtn.disabled = true;
    downloadCsvBtn.classList.add('disabled');
    
    try {
        const response = await fetch('/api/scrape', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category, location, limit, headless })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            appendLog('[System] Scraper background process started.');
            // Start Polling
            startPolling();
        } else {
            appendLog(`[System] Error starting scraper: ${result.error || 'Unknown error'}`);
            resetControlButtons();
        }
    } catch (err) {
        appendLog(`[System] Connection error: ${err.message}`);
        resetControlButtons();
    }
});

// Stop Scraping
stopBtn.addEventListener('click', async () => {
    appendLog('[System] Requesting scraper stop...');
    stopBtn.disabled = true;
    stopBtn.classList.add('disabled');
    
    try {
        const response = await fetch('/api/stop', { method: 'POST' });
        const result = await response.json();
        if (response.ok) {
            appendLog('[System] Stop signal sent.');
        } else {
            appendLog(`[System] Stop error: ${result.error}`);
        }
    } catch (err) {
        appendLog(`[System] Error sending stop request: ${err.message}`);
    }
});

// Polling Logic
function startPolling() {
    if (pollingInterval) clearInterval(pollingInterval);
    
    // Initial fetch
    fetchStatus();
    
    // Poll every 1000ms
    pollingInterval = setInterval(fetchStatus, 1000);
}

function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

async function fetchStatus() {
    try {
        const response = await fetch('/api/status');
        if (!response.ok) return;
        
        const state = await response.json();
        
        // Update Status Badge & Message
        updateStatusUI(state.status, state.message);
        
        // Update Progress Bar
        updateProgressUI(state.progress);
        
        // Merge & print new logs
        state.logs.forEach(log => {
            if (!localLogs.includes(log)) {
                localLogs.push(log);
                appendLog(log);
            }
        });
        
        // Update Leads Table & Stats if new items have been scraped
        if (state.results.length !== scrapedLeads.length || JSON.stringify(state.results) !== JSON.stringify(scrapedLeads)) {
            scrapedLeads = state.results;
            updateTableAndStats();
        }
        
        // Handle scraping completion/failure
        if (state.status !== 'running' && state.status !== 'stopping') {
            stopPolling();
            resetControlButtons();
            
            // Enable download buttons if results are present
            if (scrapedLeads.length > 0) {
                downloadXlsxBtn.disabled = false;
                downloadXlsxBtn.classList.remove('disabled');
                downloadCsvBtn.disabled = false;
                downloadCsvBtn.classList.remove('disabled');
                
                // Hook download URLs dynamically
                downloadXlsxBtn.onclick = () => window.location.href = '/api/download/xlsx';
                downloadCsvBtn.onclick = () => window.location.href = '/api/download/csv';
                
                appendLog(`[System] Scraping session finished. ${scrapedLeads.length} leads are available for download.`);
            } else {
                appendLog('[System] Scraping session finished with 0 leads. Try adjusting parameters.');
            }
        }
    } catch (err) {
        console.error('Error polling status:', err);
    }
}

function resetControlButtons() {
    startBtn.disabled = false;
    startBtn.classList.remove('disabled');
    stopBtn.disabled = true;
    stopBtn.classList.add('disabled');
}

function updateStatusUI(status, message) {
    statusBadge.textContent = status;
    
    // Reset classes
    statusBadge.className = 'status-badge';
    statusBadge.classList.add(status.toLowerCase());
    
    statusMsg.textContent = message;
}

function updateProgressUI(percent) {
    progressPercent.textContent = `${percent}%`;
    progressBarFill.style.width = `${percent}%`;
}

function updateTableAndStats() {
    // 1. Update Stats
    const totalFound = scrapedLeads.length;
    statScraped.textContent = totalFound;
    
    // Calculate Average Rating
    let ratingSum = 0;
    let ratingCount = 0;
    
    scrapedLeads.forEach(lead => {
        const r = parseFloat(lead.rating);
        if (!isNaN(r)) {
            ratingSum += r;
            ratingCount++;
        }
    });
    
    const avgRating = ratingCount > 0 ? (ratingSum / ratingCount).toFixed(1) : '-';
    statAvgRating.textContent = avgRating;
    
    // Success Rate (scraped leads out of discovered leads)
    // Here we can use the ratio of items with website or phone as a quality score,
    // or just display a progress ratio. Let's make it representation of quality leads (leads that have EITHER website or phone!)
    let qualityLeads = 0;
    scrapedLeads.forEach(lead => {
        if ((lead.website && lead.website !== 'N/A') || (lead.phone && lead.phone !== 'N/A')) {
            qualityLeads++;
        }
    });
    
    const successRate = totalFound > 0 ? Math.round((qualityLeads / totalFound) * 100) : 0;
    statSuccessRate.textContent = `${successRate}%`;
    
    // Discovered
    // Let's get total discovered from the logs or status. We'll set it in status update, or just use the length
    // Actually, let's keep discovered updated dynamically.
    // If we have total_found variable, we can fetch it. Let's look at total_found from status:
    // We can update Discovered value in status
    
    // 2. Render Table
    if (scrapedLeads.length === 0) {
        tableBody.innerHTML = `
            <tr class="empty-row">
                <td colspan="9">
                    <div class="empty-state">
                        <i class="fa-solid fa-database empty-icon"></i>
                        <p>No leads scraped yet. Start extraction to fetch leads.</p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }
    
    tableBody.innerHTML = '';
    scrapedLeads.forEach((lead, index) => {
        const row = document.createElement('tr');
        
        // Highlight rows with complete data
        const hasWeb = lead.website && lead.website !== 'N/A';
        const hasPhone = lead.phone && lead.phone !== 'N/A';
        
        row.innerHTML = `
            <td>${index + 1}</td>
            <td class="font-weight-bold" title="${lead.name}">${lead.name}</td>
            <td><span class="badge badge-outline">${lead.category}</span></td>
            <td><i class="fa-solid fa-star text-warning"></i> ${lead.rating || 'N/A'}</td>
            <td>${lead.reviews_count || '0'}</td>
            <td class="${hasPhone ? 'text-accent' : 'text-muted'}" title="${lead.phone}">${lead.phone || 'N/A'}</td>
            <td>
                ${hasWeb ? `<a href="${lead.website}" target="_blank" title="${lead.website}"><i class="fa-solid fa-globe"></i> Visit</a>` : '<span class="text-muted">N/A</span>'}
            </td>
            <td title="${lead.address}">${lead.address || 'N/A'}</td>
            <td>
                ${lead.maps_url ? `<a href="${lead.maps_url}" target="_blank" class="table-action-btn"><i class="fa-solid fa-map-location-dot"></i> Maps</a>` : '<span class="text-muted">N/A</span>'}
            </td>
        `;
        
        tableBody.appendChild(row);
    });
}

// Additional hook to fetch stats from status
async function loadInitialStats() {
    try {
        const response = await fetch('/api/status');
        if (response.ok) {
            const state = await response.json();
            statDiscovered.textContent = state.total_found || 0;
            if (state.results.length > 0) {
                scrapedLeads = state.results;
                updateTableAndStats();
                resetControlButtons();
                
                // Enable downloads
                downloadXlsxBtn.disabled = false;
                downloadXlsxBtn.classList.remove('disabled');
                downloadCsvBtn.disabled = false;
                downloadCsvBtn.classList.remove('disabled');
                downloadXlsxBtn.onclick = () => window.location.href = '/api/download/xlsx';
                downloadCsvBtn.onclick = () => window.location.href = '/api/download/csv';
                
                // Load logs
                state.logs.forEach(log => {
                    localLogs.push(log);
                    appendLog(log);
                });
            }
        }
    } catch (err) {
        console.error('Error fetching initial status:', err);
    }
}

// Initialize on page load
window.addEventListener('DOMContentLoaded', () => {
    loadInitialStats();
    
    // Periodically fetch general discovered counts if running
    setInterval(async () => {
        if (pollingInterval) {
            try {
                const response = await fetch('/api/status');
                if (response.ok) {
                    const state = await response.json();
                    statDiscovered.textContent = state.total_found || 0;
                }
            } catch(e){}
        }
    }, 1500);
});
