from flask import Flask, request, jsonify
import requests
import json
import re
import os

# --- Flask Initialization ---
# Configures Flask to look in the current directory (root) for static files.
# The static routing functions (at the bottom) handle serving assets from the 'frontend' subfolder.
app = Flask(__name__, static_folder='.', static_url_path='/')

# --- CORS (Essential for Production) ---
@app.after_request
def after_request(response):
    # Allows the frontend on checktruth.onrender.com to communicate with the API on the same domain
    header = response.headers
    header['Access-Control-Allow-Origin'] = '*'
    return response

# --- File Path Management ---
# Uses the os library to correctly find the JSON file inside the 'backend' folder
json_path = os.path.join(os.path.dirname(__file__), 'backend', 'harmful_chemicals.json')
try:
    with open(json_path, 'r') as f:
        HARMFUL_CHEMICALS = json.load(f)
except FileNotFoundError:
    print(f"WARNING: harmful_chemicals.json not found at {json_path}. Analysis will be limited.")
    HARMFUL_CHEMICALS = {}


# --- Genuine Health Score Algorithm ---
def calculate_genuine_score(product, flagged_chemicals):
    """
    Calculates a balanced health score (0-100) based on macro-nutrients and chemical risk.
    """
    nutriments = product.get('nutriments', {})
    
    # Safely get macro data (defaults to 0 if not present)
    sugars = nutriments.get('sugars_100g', 0)
    sat_fat = nutriments.get('saturated-fat_100g', 0)
    salt = nutriments.get('salt_100g', 0)
    fiber = nutriments.get('fiber_100g', 0)
    protein = nutriments.get('proteins_100g', 0)
    
    # --- 1. BASELINE SCORE (Initial 50 Points) ---
    score = 50 
    
    # --- 2. MACRO PENALTY (Max -30 points) ---
    score -= min(10, sugars / 5) 
    score -= min(10, sat_fat * 2) 
    sodium_mg = salt * 400
    score -= min(10, sodium_mg / 200)

    # --- 3. MACRO BONUS (Max +20 points) ---
    score += min(10, fiber * 2)
    score += min(10, protein * 1)

    # --- 4. CHEMICAL RISK PENALTY (Max -40 points) ---
    chemical_penalty = 0
    for chem in flagged_chemicals:
        cause = chem.get('cause', '').lower()
        avoid = chem.get('avoid', '').lower()
        
        if "carcinogen" in cause or "banned" in avoid or "toxic" in avoid:
            chemical_penalty += 8  # Severe Risk
        elif "hyperactivity" in cause or "asthma" in avoid or "allergy" in avoid:
            chemical_penalty += 5  # Moderate Risk
        elif "digestive" in cause or "caution" in avoid or "fda adverse event" in cause:
            chemical_penalty += 3  # Minor/Caution Risk
        
    score -= min(40, chemical_penalty)

    # --- 5. FINAL CLAMPING ---
    return int(max(0, min(100, score)))

# --- Layer 3: Dynamic FDA Check Function ---
def check_fda_adverse_events(ingredient_name):
    """
    Queries the openFDA API for adverse event reports related to a specific ingredient.
    """
    fda_url = "https://api.fda.gov/food/event.json"
    
    clean_name = re.sub(r'[^a-z\s]', '', ingredient_name).strip()
    if not clean_name:
        return False, ""
        
    search_term = clean_name.replace(" ", "+")
    
    query = {
        'search': f'products.ingredient.exact:{search_term}',
        'limit': 1
    }
    
    try:
        response = requests.get(fda_url, params=query, timeout=3)
        response.raise_for_status()
        data = response.json()
        
        total_reports = data.get('meta', {}).get('results', {}).get('total', 0)
        
        if total_reports > 0:
            return True, f"FDA Adverse Event Reports found ({total_reports})."
        else:
            return False, ""
    except Exception:
        return False, ""


# --- API Endpoint: Data Analysis ---
@app.route('/api/analyze/<barcode>')
def analyze_food(barcode):
    open_food_facts_url = f'https://world.openfoodfacts.org/api/v0/product/{barcode}.json'
    
    try:
        # 1. Fetch product data
        response = requests.get(open_food_facts_url)
        response.raise_for_status()
        data = response.json()
        
        if data['status'] != 1:
            return jsonify({'status': 'error', 'message': 'Product not found in the Open Food Facts database.'}), 404

        product = data['product']
        ingredients_text = product.get('ingredients_text', '').lower()
        
        flagged_chemicals = []
        disease_warnings = set()
        
        ingredients_list = [item.strip() for item in ingredients_text.split(',') if item.strip()]

        # 2. Layer 2 Check: Local Harmful Chemicals
        for key, info in HARMFUL_CHEMICALS.items():
            if re.search(r'\b' + re.escape(key) + r'\b', ingredients_text):
                flagged_chemicals.append(info)
                
                if info.get('diseases_to_avoid'):
                    for disease in info['diseases_to_avoid']:
                        disease_warnings.add(disease)
        
        # 3. Layer 3 Check: Dynamic FDA Adverse Event Lookup
        current_flagged_names = {item.get('name', '').lower() for item in flagged_chemicals}
        
        for ingredient in ingredients_list:
            if ingredient.lower() not in current_flagged_names:
                is_fda_flagged, fda_message = check_fda_adverse_events(ingredient)
                
                if is_fda_flagged:
                    flagged_chemicals.append({
                        'name': ingredient,
                        'cause': fda_message,
                        'avoid': 'Caution advised. Publicly reported adverse events exist.',
                        'diseases_to_avoid': [] 
                    })

        # 4. Calculate Final Health Score
        score = calculate_genuine_score(product, flagged_chemicals)

        # Final Response
        return jsonify({
            'status': 'success',
            'product_name': product.get('product_name', 'N/A'),
            'ingredients_text': product.get('ingredients_text', 'No ingredients listed.'),
            'flagged_chemicals': flagged_chemicals,
            'health_score': score,
            'disease_warnings': sorted(list(disease_warnings))
        })

    except requests.exceptions.RequestException as e:
        return jsonify({
            'status': 'error', 
            'message': f'Could not connect to the external API or network error: {e}'
        }), 500


# --- PRODUCTION STATIC FILE ROUTING (The Final Fix) ---

@app.route('/')
def serve_index():
    """Serves the main HTML file when the user visits the root URL."""
    return app.send_static_file('frontend/index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serves all static assets (CSS, JS, etc.) from the frontend directory."""
    # Ensure the path is relative to the frontend folder
    if filename.startswith('frontend/'):
        return app.send_static_file(filename)
    
    # Handle files requested directly from the root (like style.css, script.js)
    return app.send_static_file('frontend/' + filename)