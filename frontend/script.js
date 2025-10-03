// --- Global Elements and Configuration ---
const codeReader = new ZXing.BrowserMultiFormatReader(); 
const chatMessages = document.getElementById('chat-messages');
const scannerWrapper = document.getElementById('scanner-wrapper');
const scannerView = document.getElementById('scanner-view');
const scanButton = document.getElementById('scan-button');
const scanFeedback = document.getElementById('scan-feedback');
const mainUiContent = document.getElementById('main-ui-content'); 
const closeScannerButton = document.getElementById('close-scanner-button'); 

// --- Event Listeners and Setup ---
scanButton.addEventListener('click', () => {
    addMessage('user', 'Scan product');
    showScanner();
});

closeScannerButton.addEventListener('click', () => {
    hideScanner();
    addMessage('bot', 'Scan cancelled.');
});

document.addEventListener('DOMContentLoaded', () => {
    scannerWrapper.classList.add('hidden');
});

// --- UI Functions (No change in logic, just included for completeness) ---
function addMessage(sender, content, type = 'text') {
    mainUiContent.scrollTop = mainUiContent.scrollHeight; 
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
    chatMessages.appendChild(bubble);
    mainUiContent.scrollTop = mainUiContent.scrollHeight; 
}

function showScanner() {
    mainUiContent.classList.add('blurred'); 
    scannerWrapper.classList.remove('hidden');
    scannerView.classList.add('glowing'); 
    scanFeedback.classList.remove('hidden'); 
    scanButton.classList.add('hidden'); 
    closeScannerButton.classList.remove('hidden'); 
    
    codeReader.getVideoInputDevices().then((videoInputDevices) => {
        const rearCamera = videoInputDevices.find(device => device.label.toLowerCase().includes('back')) || videoInputDevices[0];
        const deviceId = rearCamera ? rearCamera.deviceId : undefined;
        
        codeReader.decodeFromInputVideoDevice(deviceId, 'interactive').then((result) => {
            hideScanner(); 
            addMessage('user', `Scanned: ${result.text}`);
            fetchFoodData(result.text);
        }).catch((err) => {
            console.error(err);
            if (err.name !== 'NotFoundException') { 
                addMessage('bot', '❌ Error scanning barcode. Please ensure good lighting and try again.');
            }
            hideScanner(); 
        });
    }).catch((err) => {
        console.error(err);
        hideScanner();
        addMessage('bot', '❌ Error: No camera found or permission denied. Allow camera access.');
    });
}

function hideScanner() {
    mainUiContent.classList.remove('blurred');
    scannerWrapper.classList.add('hidden');
    scannerView.classList.remove('glowing'); 
    scanFeedback.classList.add('hidden'); 
    scanButton.classList.remove('hidden'); 
    closeScannerButton.classList.add('hidden'); 
    if (codeReader) {
        codeReader.reset(); 
    }
}

// --- Data Fetching & Display (Backend Integration) ---
function fetchFoodData(barcode) {
    // FINAL FIX: Use the clean, hardcoded Render domain. 
    // This is the URL that works globally.
    const apiUrl = `https://checktruth.onrender.com/api/analyze/${barcode}`; 
    addMessage('bot', '🕵️‍♀️ Analyzing ingredients...');

    fetch(apiUrl)
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => { throw new Error(data.message || `HTTP error! Status: ${response.status}`); });
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                displayProductInfo(data);
            } else {
                addMessage('bot', `🤔 ${data.message || 'Product not found in the Open Food Facts database.'} Try another one?`);
            }
        })
        .catch(error => {
            console.error('Error fetching data from backend:', error);
            // FINAL FIX: Provide a clean error message without local IP/Port references
            addMessage('bot', `🚨 Analysis failed: The database is inaccessible, or the product barcode is unknown. (Details: ${error.message})`);
        });
}

function displayProductInfo(data) {
    const productName = data.product_name;
    const score = data.health_score;
    const healthStatus = data.health_status; // <--- CRITICAL: Capture the explicit status from the backend
    const ingredientsText = data.ingredients_text;
    const flaggedChemicals = data.flagged_chemicals; 
    const diseaseWarnings = data.disease_warnings;

    // ratingText is now redundant, but ratingColor/scoreEmoji are still needed for styling
    const ratingColor = getRatingColor(score);
    const scoreEmoji = getRatingEmoji(score);

    // --- 1. Disease Warning Box (Enhanced) ---
    let diseaseHtml = '';
    if (diseaseWarnings && diseaseWarnings.length > 0) {
        diseaseHtml = `
            <div id="disease-warning-box" style="padding: 12px; border: 2px solid var(--color-danger); border-radius: 8px; margin: 15px 0; background-color: #330000; box-shadow: 0 0 10px rgba(244, 67, 54, 0.5);">
                <h4 style="color: var(--color-warning); margin: 0 0 5px; font-size: 1.1rem; display: flex; align-items: center; gap: 8px;">
                    <i class="fas fa-exclamation-triangle"></i> 🛑 **CRITICAL HEALTH ALERT**
                </h4>
                <p style="margin: 5px 0 0; color: #FF9800; font-size: 0.95rem;">
                This product contains ingredients or levels of concern for: 
                <strong style="color: white;">${diseaseWarnings.join(' • ')}</strong>.
                </p>
                <small style="color: #ccc;">Consult a healthcare professional before consumption.</small>
            </div>
        `;
    }

    // --- 2. Health Score Header (UPDATED TO USE healthStatus) ---
    const scoreHeader = `
        <h3 style="color: ${ratingColor}; margin-bottom: 5px;">${scoreEmoji} ${productName || 'Product Name N/A'}</h3>
        <p style="font-size: 1rem; margin: 0 0 10px;">
            Overall Health Score: <strong>${healthStatus} (${score}/100)</strong>
        </p>
        <div class="rating-bar"><div class="rating-fill" style="--rating-width: ${score}%; --rating-color: ${ratingColor};"></div></div>
    `;

    // --- 3. Flagged Chemical Details (No Change) ---
    let harmfulHtml = '';
    if (flaggedChemicals.length > 0) {
        harmfulHtml = '<h4>🚨 Detailed Chemical Insights:</h4><ul id="harmful-list">';
        flaggedChemicals.forEach(item => {
            harmfulHtml += `<li class="harmful-item" style="border-left: 4px solid var(--color-danger);">
                <strong>${item.name}:</strong>
                <br><span>Cause: ${item.cause}</span>
                <br><span>Avoid if: ${item.avoid}</span>
            </li>`;
        });
        harmfulHtml += '</ul>';
    }

    // --- 4. Ingredient List (Scrollable - No Change) ---
    let ingredientsHtml = '<h4 style="margin-top: 1.5rem; border-bottom: 1px solid #444; padding-bottom: 5px;">🧬 Full Ingredient Breakdown:</h4><ul style="max-height: 150px; overflow-y: auto; padding-right: 5px;">';
    const ingredientArray = ingredientsText ? ingredientsText.split(',').map(item => item.trim()).filter(item => item.length > 0) : [];
    
    if (ingredientArray.length > 0) {
        ingredientArray.forEach(ingredient => {
            const isFlagged = flaggedChemicals.some(flagged => 
                ingredient.toLowerCase().includes(flagged.name.toLowerCase()));
            
            ingredientsHtml += `<li class="${isFlagged ? 'harmful-item' : 'safe-item'}">${ingredient}</li>`;
        });
    } else {
        ingredientsHtml += '<li>No detailed ingredients available.</li>';
    }
    ingredientsHtml += '</ul>';

    // --- Final Content Assembly ---
    const content = `
        ${scoreHeader}
        ${diseaseHtml}
        ${harmfulHtml}
        ${ingredientsHtml}
    `;

    addMessage('product', content);
}

// --- Rating Logic (Client-side display) ---
function getRatingEmoji(score) {
    if (score >= 80) return '💚';
    if (score >= 60) return '💙';
    if (score >= 40) return '💛';
    if (score >= 20) return '🧡';
    return '💔';
}

function getRatingText(score) {
    if (score >= 80) return 'Excellent';
    if (score >= 60) return 'Good';
    if (score >= 40) return 'Average';
    if (score >= 20) return 'Bad';
    return 'Awful';
}

function getRatingColor(score) {
    if (score >= 80) return '#8BC34A'; // Green
    if (score >= 60) return '#2196F3'; // Blue
    if (score >= 40) return '#FFC107'; // Amber
    if (score >= 20) return '#FF9800'; // Orange
    return '#F44336'; // Red
}

/* --- Final Code Block --- */
