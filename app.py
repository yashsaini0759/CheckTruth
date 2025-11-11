from flask import Flask, request, jsonify
import requests
import json
import re
import os

# --- Flask Initialization and Static Folder Configuration ---
app = Flask(__name__, static_folder='frontend', static_url_path='/')

# --- CORS (Essential for Production) ---
@app.after_request
def after_request(response):
    header = response.headers
    header['Access-Control-Allow-Origin'] = '*'
    return response

# --- File Path Management ---
json_path = os.path.join(os.path.dirname(__file__), 'backend', 'harmful_chemicals.json')
try:
    with open(json_path, 'r') as f:
        HARMFUL_CHEMICALS = json.load(f)
except FileNotFoundError:
    print(f"WARNING: harmful_chemicals.json not found at {json_path}. Analysis will be limited.")
    HARMFUL_CHEMICALS = {}
except json.JSONDecodeError as e:
    print(f"ERROR: Invalid JSON in harmful_chemicals.json: {e}")
    HARMFUL_CHEMICALS = {}

# --- FIXED Health Score Algorithm (Realistic Version) ---
def calculate_genuine_score(product, flagged_chemicals):
    """
    Fixed algorithm with proper error handling and realistic scoring
    """
    # Safely get nutriments with default
    nutriments = product.get('nutriments', {})
    
    # Extract nutrients safely with type conversion
    try:
        sugars = float(nutriments.get('sugars_100g', 0))
        sat_fat = float(nutriments.get('saturated-fat_100g', 0))
        sodium = float(nutriments.get('sodium_100g', 0))
        trans_fat = float(nutriments.get('trans-fat_100g', 0))
        energy = float(nutriments.get('energy-kcal_100g', 0))
        fiber = float(nutriments.get('fiber_100g', 0))
        protein = float(nutriments.get('proteins_100g', 0))
        fat = float(nutriments.get('fat_100g', 0))
        carbs = float(nutriments.get('carbohydrates_100g', 0))
    except (TypeError, ValueError) as e:
        print(f"Error parsing nutritional data: {e}")
        # Set defaults if parsing fails
        sugars = sat_fat = sodium = trans_fat = energy = fiber = protein = fat = carbs = 0

    # Start at neutral baseline
    score = 50  

    # --- PENALTIES ---
    # Sugar (very strict)
    if sugars > 30: 
        score -= 40
    elif sugars > 20: 
        score -= 30
    elif sugars > 10: 
        score -= 20
    elif sugars > 5: 
        score -= 10

    # Saturated Fat
    if sat_fat > 10: 
        score -= 20
    elif sat_fat > 5: 
        score -= 15
    elif sat_fat > 2: 
        score -= 8

    # Trans Fat (no tolerance)
    if trans_fat > 0.1: 
        score -= 25
    elif trans_fat > 0.001: 
        score -= 15  # Even small amounts are bad

    # Sodium (fixed conversion: 1g sodium = 2.5g salt)
    sodium_in_grams = sodium / 1000  # Convert mg to g
    if sodium_in_grams > 1.5: 
        score -= 20
    elif sodium_in_grams > 0.8: 
        score -= 15
    elif sodium_in_grams > 0.3: 
        score -= 8

    # Caloric density (penalize junk calories)
    if energy > 500: 
        score -= 20
    elif energy > 400: 
        score -= 15
    elif energy > 300: 
        score -= 10

    # --- BENEFITS ---
    # Protein bonus
    if protein > 10: 
        score += 15
    elif protein > 6: 
        score += 10
    elif protein > 3: 
        score += 5

    # Fiber bonus
    if fiber > 8: 
        score += 20
    elif fiber > 5: 
        score += 15
    elif fiber > 3: 
        score += 8
    elif fiber > 1: 
        score += 3

    # Balanced macros bonus (good carb-fat-protein ratio)
    if 4 < protein < 15 and 2 < fiber < 10 and sugars < 10 and sat_fat < 3:
        score += 10

    # --- CHEMICAL PENALTY ---
    chemical_penalty = 0
    if flagged_chemicals:  # Check if list exists and has items
        for chem in flagged_chemicals:
            if not isinstance(chem, dict):
                continue  # Skip invalid entries
                
            cause = chem.get('cause', '').lower()
            avoid = chem.get('avoid', '').lower()
            
            if any(word in cause for word in ['carcinogen', 'cancer', 'banned', 'toxic']):
                chemical_penalty += 15
            elif any(word in cause for word in ['hyperactivity', 'allergy', 'inflammation']):
                chemical_penalty += 10
            else:
                chemical_penalty += 5
                
        chemical_penalty = min(30, chemical_penalty)
        score -= chemical_penalty

    # --- AUTO FAIL CONDITIONS ---
    # High sugar with low nutrition
    if sugars > 25 and (protein + fiber) < 3:
        score = min(score, 25)
    
    # Trans fat presence
    if trans_fat > 0.3:
        score = min(score, 20)
    
    # High fat with low fiber
    if fat > 35 and fiber < 2:
        score = min(score, 30)
    
    # Multiple harmful chemicals
    if len(flagged_chemicals) >= 5:
        score = min(score, 20)

    # Clamp between 0 and 100
    score = max(0, min(100, int(score)))

    # --- HEALTH STATUS LABEL ---
    if score >= 85:
        status = "💚 Excellent Choice"
    elif score >= 70:
        status = "💙 Good Choice"
    elif score >= 50:
        status = "💛 Average"
    elif score >= 35:
        status = "🧡 Unhealthy"
    else:
        status = "💔 Very Unhealthy"

    # Special warnings
    if trans_fat > 0.001:
        status = "🚫 Contains Trans Fats"
    elif sugars > 20 and protein < 5:
        status = "⚠️ High Sugar Warning"

    return score, status

# --- Layer 3: Dynamic FDA Check Function (with better error handling) ---
def check_fda_adverse_events(ingredient_name):
    """
    Queries the openFDA API for adverse event reports.
    """
    if not ingredient_name or not isinstance(ingredient_name, str):
        return False, ""
        
    fda_url = "https://api.fda.gov/food/event.json"
    
    clean_name = re.sub(r'[^a-z\s]', '', ingredient_name.lower()).strip()
    if not clean_name:
        return False, ""
        
    search_term = clean_name.replace(" ", "+")
    
    query = {
        'search': f'products.ingredient.exact:{search_term}',
        'limit': 1
    }
    
    try:
        response = requests.get(fda_url, params=query, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        total_reports = data.get('meta', {}).get('results', {}).get('total', 0)
        
        if total_reports > 0:
            return True, f"FDA Adverse Event Reports found ({total_reports})."
        else:
            return False, ""
            
    except requests.exceptions.Timeout:
        return False, "FDA API timeout"
    except requests.exceptions.RequestException as e:
        return False, f"FDA API error: {str(e)}"
    except (KeyError, ValueError) as e:
        return False, f"FDA data parsing error: {str(e)}"

# --- API Endpoint: Data Analysis (with improved error handling) ---
@app.route('/api/analyze/<barcode>')
def analyze_food(barcode):
    # Validate barcode format
    if not barcode or not re.match(r'^[0-9a-zA-Z]+$', barcode):
        return jsonify({
            'status': 'error', 
            'message': 'Invalid barcode format'
        }), 400
    
    open_food_facts_url = f'https://world.openfoodfacts.org/api/v0/product/{barcode}.json'
    
    try:
        # 1. Fetch product data with timeout
        response = requests.get(open_food_facts_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') != 1:
            return jsonify({
                'status': 'error', 
                'message': 'Product not found in the Open Food Facts database.'
            }), 404

        product = data.get('product', {})
        ingredients_text = product.get('ingredients_text', '').lower()
        
        flagged_chemicals = []
        disease_warnings = set()
        
        # Safely process ingredients list
        ingredients_list = []
        if ingredients_text:
            ingredients_list = [item.strip() for item in ingredients_text.split(',') if item.strip()]

        # 2. Layer 2 Check: Local Harmful Chemicals
        for key, info in HARMFUL_CHEMICALS.items():
            if re.search(r'\b' + re.escape(key) + r'\b', ingredients_text, re.IGNORECASE):
                flagged_chemicals.append(info)
                
                diseases = info.get('diseases_to_avoid', [])
                if diseases and isinstance(diseases, list):
                    for disease in diseases:
                        if disease:  # Check for non-empty strings
                            disease_warnings.add(disease)

        # 3. Layer 3 Check: Dynamic FDA Adverse Event Lookup
        current_flagged_names = {item.get('name', '').lower() for item in flagged_chemicals if item.get('name')}
        
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
        score, health_status = calculate_genuine_score(product, flagged_chemicals)

        # Final Response
        return jsonify({
            'status': 'success',
            'product_name': product.get('product_name', 'N/A'),
            'ingredients_text': ingredients_text if ingredients_text else 'No ingredients listed.',
            'flagged_chemicals': flagged_chemicals,
            'health_score': score,
            'health_status': health_status,
            'disease_warnings': sorted(list(disease_warnings))
        })

    except requests.exceptions.Timeout:
        return jsonify({
            'status': 'error', 
            'message': 'Request timeout: Could not connect to food database.'
        }), 408
    except requests.exceptions.RequestException as e:
        return jsonify({
            'status': 'error', 
            'message': f'Network error: Could not connect to external API. ({str(e)})'
        }), 500
    except Exception as e:
        return jsonify({
            'status': 'error', 
            'message': f'Unexpected error: {str(e)}'
        }), 500

# --- PRODUCTION STATIC FILE ROUTING ---
@app.route('/')
def serve_index():
    return app.send_static_file('index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return app.send_static_file(filename)

if __name__ == '__main__':
    app.run(debug=True)