// DeepStock Frontend JavaScript

// Initialize page when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializePage();
});

function initializePage() {
    // Show main content immediately since user is already authenticated
    const mainContent = document.getElementById('mainContent');
    if (mainContent) {
        mainContent.style.display = 'flex';
        setTimeout(() => mainContent.classList.add('visible'), 10);
    }
    
    // Load preview data
    loadPreviewData();
    
    // Initialize event listeners
    initializeEventListeners();
    
    // Initialize search enhancements
    initializeSearchEnhancements();
}

function initializeEventListeners() {
    // Search form submission
    const searchForm = document.querySelector('.search-form');
    if (searchForm) {
        searchForm.addEventListener('submit', handleFormSubmission);
    }

    // User dropdown toggle
    const userAvatar = document.querySelector('.user-avatar');
    if (userAvatar) {
        userAvatar.addEventListener('click', toggleUserDropdown);
    }

    // Close dropdown when clicking outside
    document.addEventListener('click', handleOutsideClick);

    // Logout handler
    const logoutBtn = document.querySelector('.dropdown-item[href="/logout"]');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }

    // Stock row click handlers
    document.addEventListener('click', handleStockRowClick);
}

function handleFormSubmission(e) {
    const input = document.querySelector('input[name="stock_name"]');
    const value = input.value.trim();
    
    if (!value) {
        e.preventDefault();
        showInputError(input, 'Please enter a stock name or symbol');
        return false;
    }
    
    // Show loading state
    showLoadingState();
}

function showInputError(input, message) {
    input.style.borderColor = '#dc2626';
    input.placeholder = message;
    input.focus();
    
    setTimeout(() => {
        input.style.borderColor = '';
        input.placeholder = 'Search for any Indian stock...';
    }, 3000);
}

function showLoadingState() {
    const loader = document.querySelector('.loader');
    const submitBtn = document.querySelector('.search-form input[type="submit"]');
    
    if (loader) {
        loader.classList.add('active');
    }
    
    if (submitBtn) {
        submitBtn.value = 'Analyzing...';
        submitBtn.disabled = true;
    }
}

function toggleUserDropdown(e) {
    e.stopPropagation();
    const dropdown = document.querySelector('.dropdown-menu');
    if (dropdown) {
        dropdown.classList.toggle('active');
    }
}

function handleOutsideClick(e) {
    if (!e.target.closest('.user-menu')) {
        const dropdown = document.querySelector('.dropdown-menu');
        if (dropdown) {
            dropdown.classList.remove('active');
        }
    }
}

function handleLogout(e) {
    e.preventDefault();
    // Add confirmation dialog
    if (confirm('Are you sure you want to logout?')) {
        window.location.href = '/logout';
    }
}

function handleStockRowClick(e) {
    const row = e.target.closest('tr[onclick]');
    if (row && row.cells && row.cells.length > 1) {
        const symbol = row.cells[1].textContent.trim();
        selectStock(symbol);
    }
}

// Function to load and display preview data
async function loadPreviewData() {
    const tableBody = document.getElementById('previewTableBody');
    if (!tableBody) return;
    
    // Show loading state
    showTableLoading(tableBody);

    try {
        const text = await fetchStockData();
        const rows = parseStockData(text);
        
        if (rows.length === 0) {
            throw new Error('No stock data available');
        }
        
        renderStockTable(tableBody, rows);
        
    } catch (error) {
        console.error('Error loading stock data:', error);
        showTableError(tableBody);
    }
}

function showTableLoading(tableBody) {
    tableBody.innerHTML = `
        <tr>
            <td colspan="5">
                <div class="table-loader">
                    <div class="loader active">
                        <div class="dot"></div>
                        <div class="dot"></div>
                        <div class="dot"></div>
                    </div>
                    <div style="margin-top: 1rem;">Loading stocks...</div>
                </div>
            </td>
        </tr>
    `;
}

async function fetchStockData() {
    // Try multiple paths for the CSV file
    const paths = ['/static/ind_nifty500list.csv', '/ind_nifty500list.csv'];
    
    for (const path of paths) {
        try {
            const response = await fetch(path);
            if (response.ok) {
                return await response.text();
            }
        } catch (error) {
            console.warn(`Failed to fetch from ${path}:`, error);
        }
    }
    
    throw new Error('Failed to load stock data from any source');
}

function parseStockData(text) {
    return text.split('\n')
        .slice(1) // Skip header
        .filter(row => row.trim())
        .map(row => row.split(','))
        .filter(columns => columns.length >= 5);
}

function renderStockTable(tableBody, rows) {
    tableBody.innerHTML = rows.slice(0, 15).map(columns => {
        const [company, industry, symbol, series, isin] = columns.map(col => col.trim());
        return `
            <tr onclick="selectStock('${symbol}')">
                <td class="company-name">${escapeHtml(company)}</td>
                <td>${escapeHtml(symbol)}</td>
                <td>${escapeHtml(industry)}</td>
                <td>${escapeHtml(series)}</td>
                <td>${escapeHtml(isin)}</td>
            </tr>
        `;
    }).join('');
}

function showTableError(tableBody) {
    tableBody.innerHTML = `
        <tr>
            <td colspan="5" style="text-align:center; padding: 2rem;">
                <div style="color: #dc2626; margin-bottom: 1rem;">
                    Unable to load stock data
                </div>
                <button onclick="loadPreviewData()" class="retry-btn">
                    Retry
                </button>
            </td>
        </tr>
    `;
}

// Function to select a stock from the table
function selectStock(symbol) {
    const searchInput = document.querySelector('input[name="stock_name"]');
    if (searchInput) {
        searchInput.value = symbol;
        searchInput.focus();
        
        // Add visual feedback
        searchInput.style.borderColor = '#10b981';
        setTimeout(() => {
            searchInput.style.borderColor = '';
        }, 1000);
    }
}

function initializeSearchEnhancements() {
    const searchInput = document.querySelector('input[name="stock_name"]');
    if (!searchInput) return;
    
    // Add placeholder animation
    initializePlaceholderAnimation(searchInput);
    
    // Add input validation
    searchInput.addEventListener('input', handleInputValidation);
}

function initializePlaceholderAnimation(searchInput) {
    const placeholders = [
        'Search for any Indian stock...',
        'Try "RELIANCE" or "TCS"...',
        'Enter company name or symbol...'
    ];
    let currentIndex = 0;
    
    setInterval(() => {
        if (searchInput === document.activeElement || searchInput.value.trim()) return;
        currentIndex = (currentIndex + 1) % placeholders.length;
        searchInput.placeholder = placeholders[currentIndex];
    }, 3000);
}

function handleInputValidation(e) {
    const value = e.target.value.trim();
    if (value.length > 0) {
        e.target.style.borderColor = '#6366f1';
    } else {
        e.target.style.borderColor = '';
    }
}

// Utility function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Add CSS for retry button
const style = document.createElement('style');
style.textContent = `
    .retry-btn {
        background: #6366f1;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 6px;
        cursor: pointer;
        font-size: 0.9rem;
        transition: all 0.2s ease;
    }
    
    .retry-btn:hover {
        background: #4f46e5;
        transform: translateY(-1px);
    }
`;
document.head.appendChild(style);

// Export functions for global access
window.loadPreviewData = loadPreviewData;
window.selectStock = selectStock;