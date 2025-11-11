// ==================== GLOBAL CONFIGURATION ====================
const codeReader = new ZXing.BrowserMultiFormatReader();

// DOM Elements
const elements = {
    chatMessages: document.getElementById('chat-messages'),
    scannerWrapper: document.getElementById('scanner-wrapper'),
    scannerView: document.getElementById('scanner-view'),
    scanButton: document.getElementById('scan-button'),
    scanFeedback: document.getElementById('scan-feedback'),
    mainUiContent: document.getElementById('main-ui-content'),
    closeScannerButton: document.getElementById('close-scanner-button')
};

// ==================== EVENT LISTENERS ====================
document.addEventListener('DOMContentLoaded', initializeApp);
elements.scanButton.addEventListener('click', handleScanClick);
elements.closeScannerButton.addEventListener('click', handleCloseScanner);

// ==================== INITIALIZATION ====================
function initializeApp() {
    elements.scannerWrapper.classList.add('hidden');
    console.log('CheckTruth initialized successfully');
}

// ==================== EVENT HANDLERS ====================
function handleScanClick() {
    addMessage('user', 'Scan product');
    showScanner();
}

function handleCloseScanner() {
    hideScanner();
    addMessage('bot', '🔍 Scan cancelled. Ready to scan another product!');
}

// ==================== UI FUNCTIONS ====================
/**
 * Add a message to the chat interface
 * @param {string} sender - 'user', 'bot', or 'product'
 * @param {string} content - Message content (HTML for product)
 * @param {string} type - Message type (default: 'text')
 */
function addMessage(sender, content, type = 'text') {
    const bubble = document.createElement('div');
    bubble.classList.add('chat-bubble');
    
    if (sender === 'bot') {
        bubble.classList.add('bot-bubble');
        bubble.innerHTML = `<p>${content}</p>`;
    } else if (sender === 'user') {
        bubble.classList.add('user-bubble');
        bubble.innerHTML = `<p>${content}</p>`;
    } else if (sender === 'product') {
        bubble.classList.add('product-result-bubble');
        bubble.innerHTML = content;
    }
    
    elements.chatMessages.appendChild(bubble);
    scrollToBottom();
}

/**
 * Scroll chat to bottom smoothly
 */
function scrollToBottom() {
    setTimeout(() => {
        elements.mainUiContent.scrollTo({
            top: elements.mainUiContent.scrollHeight,
            behavior: 'smooth'
        });
    }, 100);
}

// ==================== SCANNER FUNCTIONS ====================
/**
 * Show the barcode scanner overlay
 */
function showScanner() {
    elements.mainUiContent.classList.add('blurred');
    elements.scannerWrapper.classList.remove('hidden');
    elements.scanButton.classList.add('hidden');
    elements.closeScannerButton.classList.remove('hidden');
    
    initializeBarcodeScanner();
}

/**
 * Hide the barcode scanner overlay
 */
function hideScanner() {
    elements.mainUiContent.classList.remove('blurred');
    elements.scannerWrapper.classList.add('hidden');
    elements.scanButton.classList.remove('hidden');
    elements.closeScannerButton.classList.add('hidden');
    
    if (codeReader) {
        codeReader.reset();
    }
}

/**
 * Initialize and start barcode scanning
 */
function initializeBarcodeScanner() {
    codeReader.getVideoInputDevices()
        .then((videoInputDevices) => {
            if (videoInputDevices.length === 0) {
                throw new Error('No camera found');
            }
            
            // Prefer rear camera
            const rearCamera = videoInputDevices.find(device => 
                device.label.toLowerCase().includes('back')
            ) || videoInputDevices[0];
            
            const deviceId = rearCamera ? rearCamera.deviceId : undefined;
            
            return codeReader.decodeFromInputVideoDevice(deviceId, 'interactive');
        })
        .then((result) => {
            handleSuccessfulScan(result.text);
        })
        .catch((err) => {
            handleScanError(err);
        });
}

/**
 * Handle successful barcode scan
 * @param {string} barcode - Scanned barcode text
 */
function handleSuccessfulScan(barcode) {
    hideScanner();
    addMessage('user', `Scanned: ${barcode}`);
    fetchFoodData(barcode);
}

/**
 * Handle scanner errors
 * @param {Error} err - Error object
 */
function handleScanError(err) {
    console.error('Scanner error:', err);
    hideScanner();
    
    if (err.message.includes('No camera found') || err.name === 'NotAllowedError') {
        addMessage('bot', '📷 Camera access denied. Please allow camera permissions in your browser settings.');
    } else if (err.name !== 'NotFoundException') {
        addMessage('bot', '❌ Scanning error. Please ensure good lighting and try again.');
    }
}

// ==================== DATA FETCHING ====================
/**
 * Fetch food data from backend API
 * @param {string} barcode - Product barcode
 */
function fetchFoodData(barcode) {
    const apiUrl = `https://checktruth.onrender.com/api/analyze/${barcode}`;
    
    addMessage('bot', '🔬 Analyzing ingredients and nutrition data...');
    
    fetch(apiUrl)
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.message || `HTTP ${response.status}`);
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                displayProductInfo(data);
            } else {
                addMessage('bot', `🤔 ${data.message || 'Product not found in database.'} Try scanning another product!`);
            }
        })
        .catch(error => {
            console.error('API Error:', error);
            addMessage('bot', `🚨 Analysis failed: ${error.message}. The database may be temporarily unavailable.`);
        });
}

// ==================== PRODUCT DISPLAY ====================
/**
 * Display comprehensive product information
 * @param {Object} data - Product data from API
 */
function displayProductInfo(data) {
    const {
        product_name,
        health_score,
        health_status,
        ingredients_text,
        flagged_chemicals,
        disease_warnings,
        nutrition_facts
    } = data;
    
    const ratingColor = getRatingColor(health_score);
    const scoreEmoji = getRatingEmoji(health_score);
    
    // Build HTML sections
    const sections = [
        buildScoreHeader(product_name, health_status, health_score, scoreEmoji, ratingColor),
        buildDiseaseWarning(disease_warnings),
        buildNutritionGrid(nutrition_facts),
        buildChemicalInsights(flagged_chemicals),
        buildIngredientsList(ingredients_text, flagged_chemicals)
    ].filter(Boolean); // Remove empty sections
    
    const content = sections.join('');
    addMessage('product', content);
}

/**
 * Build health score header section
 */
function buildScoreHeader(productName, healthStatus, score, emoji, color) {
    return `
        <h3 style="color: ${color}; margin-bottom: 0.5rem; font-size: 1.25rem;">
            ${emoji} ${productName || 'Product Name Unavailable'}
        </h3>
        <p style="font-size: 1rem; margin: 0.5rem 0; color: ${color};">
            <strong>${healthStatus}</strong> (${score}/100)
        </p>
        <div class="rating-bar">
            <div class="rating-fill" style="--rating-width: ${score}%; --rating-color: ${color};"></div>
        </div>
    `;
}

/**
 * Build disease warning section
 */
function buildDiseaseWarning(warnings) {
    if (!warnings || warnings.length === 0) return '';
    
    return `
        <div id="disease-warning-box">
            <h4>
                <i class="fas fa-exclamation-triangle"></i>
                HEALTH ALERT
            </h4>
            <p>
                This product contains ingredients linked to: 
                <strong>${warnings.join(' • ')}</strong>
            </p>
            <small>⚕️ Consult healthcare professional before consumption</small>
        </div>
    `;
}

/**
 * Build nutrition facts grid
 */
function buildNutritionGrid(nutritionFacts) {
    if (!nutritionFacts) return '';
    
    const nutritionItems = [
        { key: 'calories', label: 'Calories', unit: 'kcal', highlight: (v) => v > 400 },
        { key: 'protein', label: 'Protein', unit: 'g', positive: true },
        { key: 'carbohydrates', label: 'Carbs', unit: 'g' },
        { key: 'sugars', label: 'Sugars', unit: 'g', highlight: (v) => v > 15 },
        { key: 'added_sugars', label: 'Added Sugars', unit: 'g', highlight: (v) => v > 0 },
        { key: 'fiber', label: 'Fiber', unit: 'g', positive: true },
        { key: 'fat', label: 'Fat', unit: 'g' },
        { key: 'saturated_fat', label: 'Sat. Fat', unit: 'g', highlight: (v) => v > 5 },
        { key: 'trans_fat', label: 'Trans Fat', unit: 'g', highlight: (v) => v > 0 },
        { key: 'sodium', label: 'Sodium', unit: 'mg', highlight: (v) => v > 800 }
    ];
    
    let gridHtml = '<h4>📊 Nutrition Facts (per 100g)</h4><div class="nutrition-grid">';
    
    nutritionItems.forEach(item => {
        const value = nutritionFacts[item.key];
        if (value !== undefined && value !== null) {
            let cssClass = '';
            
            if (item.highlight && item.highlight(value)) {
                cssClass = 'nutrition-highlight';
            } else if (item.positive && value > 0) {
                cssClass = 'nutrition-positive';
            }
            
            gridHtml += `
                <div class="nutrition-item ${cssClass}">
                    <span>${item.label}</span>
                    <span class="nutrition-value">${value}${item.unit}</span>
                </div>
            `;
        }
    });
    
    gridHtml += '</div>';
    return gridHtml;
}

/**
 * Build chemical insights section
 */
function buildChemicalInsights(flaggedChemicals) {
    if (!flaggedChemicals || flaggedChemicals.length === 0) {
        return '<h4>✅ No Concerning Chemicals Detected</h4><p style="color: #4CAF50;">This product appears safe based on current ingredient analysis.</p>';
    }
    
    let html = '<h4>🚨 Concerning Ingredients Found</h4><ul id="harmful-list">';
    
    flaggedChemicals.forEach(item => {
        const riskLevel = item.risk_level || 'medium';
        const riskClass = `risk-badge risk-${riskLevel}`;
        
        html += `
            <li class="harmful-item">
                <strong>${item.name}</strong> 
                <span class="${riskClass}">${riskLevel.toUpperCase()}</span>
                <br><small style="color: #FFB74D;">⚠️ ${item.cause}</small>
                <br><small style="color: #EF9A9A;">🚫 Avoid if: ${item.avoid}</small>
            </li>
        `;
    });
    
    html += '</ul>';
    return html;
}

/**
 * Build complete ingredients list
 */
function buildIngredientsList(ingredientsText, flaggedChemicals) {
    const ingredientArray = ingredientsText 
        ? ingredientsText.split(',').map(item => item.trim()).filter(item => item.length > 0)
        : [];
    
    if (ingredientArray.length === 0) {
        return '<h4>🧬 Ingredients</h4><p style="color: #B0B0B0;">No detailed ingredient list available.</p>';
    }
    
    let html = '<h4>🧬 Complete Ingredient List</h4><ul style="max-height: 200px; overflow-y: auto; padding-right: 5px;">';
    
    ingredientArray.forEach(ingredient => {
        const isFlagged = flaggedChemicals.some(flagged =>
            ingredient.toLowerCase().includes(flagged.name.toLowerCase())
        );
        
        const itemClass = isFlagged ? 'harmful-item' : 'safe-item';
        html += `<li class="${itemClass}">${ingredient}</li>`;
    });
    
    html += '</ul>';
    return html;
}

// ==================== RATING UTILITIES ====================
/**
 * Get emoji based on health score
 * @param {number} score - Health score (0-100)
 * @returns {string} Emoji
 */
function getRatingEmoji(score) {
    if (score >= 80) return '💚';
    if (score >= 60) return '💙';
    if (score >= 40) return '💛';
    if (score >= 20) return '🧡';
    return '💔';
}

/**
 * Get color based on health score
 * @param {number} score - Health score (0-100)
 * @returns {string} Hex color
 */
function getRatingColor(score) {
    if (score >= 80) return '#8BC34A'; // Green
    if (score >= 60) return '#2196F3'; // Blue
    if (score >= 40) return '#FFC107'; // Amber
    if (score >= 20) return '#FF9800'; // Orange
    return '#F44336'; // Red
}