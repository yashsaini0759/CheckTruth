from flask import Flask, request, jsonify
import requests
import json
import re

app = Flask(__name__)

# This allows your frontend (e.g., on port 5501) to communicate with this backend (port 5000)
# essential for development.
@app.after_request
def after_request(response):
    header = response.headers
    # Sets the Access-Control-Allow-Origin header to allow requests from any domain/port
    header['Access-Control-Allow-Origin'] = '*'
    return response

# Load your local database of known chemicals, now including disease warnings
try:
    with open('harmful_chemicals.json', 'r') as f:
        HARMFUL_CHEMICALS = json.load(f)
except FileNotFoundError:
    print("WARNING: harmful_chemicals.json not found. Analysis will be limited.")
    HARMFUL_CHEMICALS = {}

# --- Layer 3: Dynamic FDA Check Function ---
def check_fda_adverse_events(ingredient_name):
    """
    Queries the openFDA API for adverse event reports related to a specific ingredient.
    """
    fda_url = "https://api.fda.gov/food/event.json"
    
    # Clean the name for the query: use only alpha characters for a better search match
    clean_name = re.sub(r'[^a-z\s]', '', ingredient_name).strip()
    if not clean_name:
        return False, ""
        
    # Search the 'products.ingredient' field for the cleaned ingredient name
    search_term = clean_name.replace(" ", "+")
    
    query = {
        'search': f'products.ingredient.exact:{search_term}',
        'limit': 1  # We only need to know if at least one report exists
    }
    
    try:
        # We don't need an API key for basic searches, but we set a timeout.
        response = requests.get(fda_url, params=query, timeout=3)
        response.raise_for_status()
        data = response.json()
        
        # Check the total number of adverse event reports found
        total_reports = data.get('meta', {}).get('results', {}).get('total', 0)
        
        if total_reports > 0:
            return True, f"FDA Adverse Event Reports found ({total_reports})."
        else:
            return False, ""
    except Exception:
        # Fails silently if the FDA API is down, returns an error, or times out
        return False, ""

# --- Main API Endpoint ---
@app.route('/api/analyze/<barcode>')
def analyze_food(barcode):
    """
    Analyzes a food product by its barcode using Open Food Facts and custom rules.
    """
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
        
        # Split ingredients for a more accurate loop (simplified list for FDA check)
        ingredients_list = [item.strip() for item in ingredients_text.split(',') if item.strip()]

        # 2. Layer 2 Check: Local Harmful Chemicals (The Core Analysis)
        for key, info in HARMFUL_CHEMICALS.items():
            # Use regex to find whole words/phrases for a robust match
            if re.search(r'\b' + re.escape(key) + r'\b', ingredients_text):
                # Add the chemical's full details to the flagged list
                flagged_chemicals.append(info)
                
                # Aggregate specific disease warnings (NEW FEATURE)
                if info.get('diseases_to_avoid'):
                    for disease in info['diseases_to_avoid']:
                        disease_warnings.add(disease)
        
        # 3. Layer 3 Check: Dynamic FDA Adverse Event Lookup
        # Perform a check only on the unique, unflagged ingredients
        current_flagged_names = {item.get('name', '').lower() for item in flagged_chemicals}
        
        for ingredient in ingredients_list:
            if ingredient not in current_flagged_names:
                is_fda_flagged, fda_message = check_fda_adverse_events(ingredient)
                
                if is_fda_flagged:
                    # Add a dynamic warning to the list
                    flagged_chemicals.append({
                        'name': ingredient,
                        'cause': fda_message,
                        'avoid': 'Caution advised. Publicly reported adverse events exist.',
                        'diseases_to_avoid': [] # No specific disease linkage from FDA reports
                    })

        # 4. Calculate Final Health Score
        score = 100
        
        # Base Score from Open Food Facts Nutri-Score (if available)
        if product.get('nutriscore_grade'):
            nutriscore = product['nutriscore_grade'].lower()
            score_map = {'a': 90, 'b': 75, 'c': 50, 'd': 25, 'e': 10}
            score = score_map.get(nutriscore, score)
        
        # Penalize for each specific harmful chemical found
        score -= len(flagged_chemicals) * 10 
        
        # Ensure score stays within the 0-100 bounds
        score = max(0, min(100, score))

        # Final Response
        return jsonify({
            'status': 'success',
            'product_name': product.get('product_name', 'N/A'),
            'ingredients_text': product.get('ingredients_text', 'No ingredients listed.'),
            'flagged_chemicals': flagged_chemicals,
            'health_score': score,
            'disease_warnings': sorted(list(disease_warnings)) # Send back a sorted unique list
        })

    except requests.exceptions.RequestException as e:
        return jsonify({
            'status': 'error', 
            'message': f'Could not connect to the external API or network error: {e}'
        }), 500

if __name__ == '__main__':
    # Running on 0.0.0.0 allows connection from your mobile phone's IP
    app.run(host='0.0.0.0', port=5000, debug=True)