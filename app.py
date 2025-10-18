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

# --- FIXED Health Score Algorithm (Realistic Version) ---
def calculate_genuine_score(product, flagged_chemicals):
    """
    Calculates a realistic health score (0-100) with proper penalties for unhealthy foods.
    """
    nutriments = product.get('nutriments', {})
    
    # --- Safely Get Nutritional Metrics (Defaults to 0) ---
    sugars = nutriments.get('sugars_100g', 0)
    sat_fat = nutriments.get('saturated-fat_100g', 0)
    sodium = nutriments.get('sodium_100g', 0)
    trans_fat = nutriments.get('trans-fat_100g', 0)
    energy_kcal = nutriments.get('energy-kcal_100g', 0)
    total_fat = nutriments.get('fat_100g', 0)
    carbohydrates = nutriments.get('carbohydrates_100g', 0)
    fiber = nutriments.get('fiber_100g', 0)
    protein = nutriments.get('proteins_100g', 0)
    
    # --- 1. START FROM 0 AND BUILD UP (Not from 100 down) ---
    score = 0
    
    # --- 2. CRITICAL FLAW FIX: MAJOR PENALTIES FOR UNHEALTHY COMPONENTS ---
    
    # A. SUGAR PENALTY (Very Aggressive - Sugar is the #1 concern)
    # WHO recommends max 25g sugar daily - 10g/100g is already high
    sugar_penalty = 0
    if sugars > 20:
        sugar_penalty = 40  # Extremely high sugar
    elif sugars > 15:
        sugar_penalty = 30
    elif sugars > 10:
        sugar_penalty = 20
    elif sugars > 5:
        sugar_penalty = 10
    
    # B. SATURATED FAT PENALTY
    sat_fat_penalty = 0
    if sat_fat > 5:
        sat_fat_penalty = 15
    elif sat_fat > 3:
        sat_fat_penalty = 10
    elif sat_fat > 1:
        sat_fat_penalty = 5
    
    # C. SODIUM PENALTY
    sodium_penalty = 0
    if sodium > 1.0:  # >1g sodium per 100g is very high
        sodium_penalty = 15
    elif sodium > 0.5:
        sodium_penalty = 10
    elif sodium > 0.2:
        sodium_penalty = 5
    
    # D. TRANS FAT PENALTY (Zero tolerance)
    trans_fat_penalty = 20 if trans_fat > 0.1 else 0
    
    # E. CALORIE DENSITY PENALTY (Empty calories)
    calorie_penalty = 0
    if energy_kcal > 400 and (protein + fiber) < 5:
        calorie_penalty = 15  # High calories, low nutrition
    elif energy_kcal > 300 and (protein + fiber) < 3:
        calorie_penalty = 10
    
    # Apply penalties (they reduce from maximum possible)
    max_possible_score = 100
    penalty_total = sugar_penalty + sat_fat_penalty + sodium_penalty + trans_fat_penalty + calorie_penalty
    
    # --- 3. NUTRITIONAL BENEFITS (Add points for good components) ---
    
    nutritional_benefits = 0
    
    # A. PROTEIN BONUS
    protein_bonus = min(15, protein * 2)  # Max 15 points
    
    # B. FIBER BONUS (Very important)
    fiber_bonus = min(20, fiber * 4)  # Max 20 points
    
    # C. HEALTHY RATIO BONUS (Good balance)
    balance_bonus = 0
    if protein > 5 and fiber > 3 and sugars < 8:
        balance_bonus = 10
    
    nutritional_benefits = protein_bonus + fiber_bonus + balance_bonus
    
    # --- 4. CHEMICAL & ADDITIVE PENALTIES ---
    chemical_penalty = 0
    
    for chem in flagged_chemicals:
        cause = chem.get('cause', '').lower()
        avoid = chem.get('avoid', '').lower()
        
        if "carcinogen" in cause or "banned" in avoid:
            chemical_penalty += 10
        elif "hyperactivity" in cause or "toxic" in avoid:
            chemical_penalty += 7
        else:
            chemical_penalty += 3
    
    # Cap chemical penalty
    chemical_penalty = min(25, chemical_penalty)
    
    # --- 5. CALCULATE FINAL SCORE ---
    # Start from max, subtract penalties, add benefits (but benefits can't overcome major penalties)
    base_score = max_possible_score - penalty_total
    final_score = base_score + nutritional_benefits - chemical_penalty
    
    # Ensure score is realistic - no sugary drinks should score high
    # CRITICAL FIX: Automatic fail for very high sugar, low nutrition products
    if sugars > 15 and (protein + fiber) < 2:
        final_score = min(final_score, 30)  # Cap at 30 no matter what
    
    if sugars > 25:  # Extremely high sugar
        final_score = min(final_score, 20)
    
    # Final clamping
    final_score = int(max(0, min(100, final_score)))
    
    # --- 6. REALISTIC HEALTH STATUS ---
    health_status = ""
    if final_score >= 80 and fiber >= 5 and sugars <= 5 and sat_fat <= 3:
        health_status = "💚 Excellent Choice"
    elif final_score >= 65 and fiber >= 3 and sugars <= 8:
        health_status = "💙 Good Choice" 
    elif final_score >= 45:
        health_status = "💛 Average"
    elif final_score >= 30:
        health_status = "🧡 Below Average"
    else:
        health_status = "💔 Poor Choice"
    
    # Special cases that automatically get poor ratings
    if sugars > 20 and protein < 2:
        health_status = "💔 High Sugar Warning"
    if trans_fat > 0.5:
        health_status = "💔 Contains Trans Fats"
    
    return final_score, health_status

# --- Layer 3: Dynamic FDA Check Function (unchanged) ---
def check_fda_adverse_events(ingredient_name):
    """
    Queries the openFDA API for adverse event reports.
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

# --- API Endpoint: Data Analysis (unchanged) ---
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

        # 4. Calculate Final Health Score (USING FIXED ALGORITHM)
        score, health_status = calculate_genuine_score(product, flagged_chemicals)

        # Final Response
        return jsonify({
            'status': 'success',
            'product_name': product.get('product_name', 'N/A'),
            'ingredients_text': product.get('ingredients_text', 'No ingredients listed.'),
            'flagged_chemicals': flagged_chemicals,
            'health_score': score,
            'health_status': health_status,
            'disease_warnings': sorted(list(disease_warnings))
        })

    except requests.exceptions.RequestException as e:
        return jsonify({
            'status': 'error', 
            'message': f'Could not connect to the external API or network error: {e}'
        }), 500

# --- PRODUCTION STATIC FILE ROUTING ---
@app.route('/')
def serve_index():
    return app.send_static_file('index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return app.send_static_file(filename)