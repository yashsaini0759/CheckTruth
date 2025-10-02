from flask import Flask, request, jsonify
import requests
import json
import re
import os # Import os for file path management

app = Flask(__name__)

# --- CORS (Essential for Development) ---
@app.after_request
def after_request(response):
    header = response.headers
    header['Access-Control-Allow-Origin'] = '*'
    return response

# --- File Path Management ---
# Use the correct path for the JSON file now that app.py is in the root (for PythonAnywhere)
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
    
    # A. SUGAR PENALTY: (Max -10)
    score -= min(10, sugars / 5) # Deduct 1 point per 5g of sugar/100g
    
    # B. SATURATED FAT PENALTY: (Max -10)
    score -= min(10, sat_fat * 2) # Deduct 2 points per 1g of saturated fat/100g
    
    # C. SODIUM/SALT PENALTY: (Max -10)
    # Convert salt (grams) to sodium (milligrams) for a fairer penalty (Salt * 400 = Sodium mg)
    sodium_mg = salt * 400
    score -= min(10, sodium_mg / 200) # Deduct 1 point per 200mg of sodium/100g

    # --- 3. MACRO BONUS (Max +20 points) ---
    
    # D. FIBER BONUS: (Max +10)
    score += min(10, fiber * 2) # Add 2 points per 1g of fiber/100g

    # E. PROTEIN BONUS: (Max +10)
    score += min(10, protein * 1) # Add 1 point per 1g of protein/100g

    # --- 4. CHEMICAL RISK PENALTY (Max -40 points) ---
    chemical_penalty = 0
    
    for chem in flagged_chemicals:
        # Penalize less for general warnings (like FDA reports) and more for known toxic additives
        cause = chem.get('cause', '').lower()
        avoid = chem.get('avoid', '').lower()
        
        if "carcinogen" in cause or "banned" in avoid or "toxic" in avoid:
            chemical_penalty += 8  # Severe Risk (e.g., Potassium Bromate, Illegal Dyes)
        elif "hyperactivity" in cause or "asthma" in avoid or "allergy" in avoid:
            chemical_penalty += 5  # Moderate Risk (e.g., Artificial Dyes, Sulfites)
        elif "digestive" in cause or "caution" in avoid or "fda adverse event" in cause:
            chemical_penalty += 3  # Minor/Caution Risk
        
    score -= min(40, chemical_penalty)

    # --- 5. FINAL CLAMPING ---
    # Ensure the final score is between 0 and 100
    return int(max(0, min(100, score)))

# --- Layer 3: Dynamic FDA Check Function (Same as before) ---
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


# --- Main API Endpoint ---
@app.route('/api/analyze/<barcode>')
def analyze_food(barcode):
    open_food_facts_url = f'https://world.openfoodfacts.org/api/v0/product/{barcode}.json'
    
    try:
        # 1. Fetch product data from Open Food Facts API
        response = requests.get(open_food_facts_url)
        response.raise_for_status()
        data = response.json()
        
        if data['status'] != 1:
            return jsonify({'status': 'error', 'message': 'Product not found in the Open Food Facts database.'}), 404

        product = data['product']
        ingredients_text = product.get('ingredients_text', '').lower()
        
        # Initialize lists for dynamic analysis results
        flagged_chemicals = []
        disease_warnings = set()
        
        # Prepare ingredient list for looping
        ingredients_list = [item.strip() for item in ingredients_text.split(',') if item.strip()]

        # 2. Layer 2 Check: Local Harmful Chemicals (The Core Analysis)
        for key, info in HARMFUL_CHEMICALS.items():
            if re.search(r'\b' + re.escape(key) + r'\b', ingredients_text):
                flagged_chemicals.append(info)
                
                # Aggregate specific disease warnings 
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

        # 4. Calculate Final Health Score using the new genuine algorithm
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

if __name__ == '__main__':
    # This block is used for local development testing only
    app.run(host='0.0.0.0', port=5000, debug=True)