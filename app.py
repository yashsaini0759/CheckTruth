from flask import Flask, request, jsonify
import requests
import json
import re
import os

# --- Flask Initialization and Static Folder Configuration ---
# CRITICAL FIX: Set static_folder to 'frontend'. This tells Flask where the HTML/CSS/JS live.
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


# --- Genuine Health Score Algorithm (CheckTruth v7.0) ---
def calculate_genuine_score(product, flagged_chemicals):
    """
    Calculates a balanced health score (0-100) using 25+ macros/micros and weighted chemical risk.
    """
    nutriments = product.get('nutriments', {})
    
    # --- Safely Get 25+ Nutritional Metrics (Defaults to 0) ---
    sugars = nutriments.get('sugars_100g', 0)
    sat_fat = nutriments.get('saturated-fat_100g', 0)
    sodium = nutriments.get('sodium_100g', 0)
    trans_fat = nutriments.get('trans-fat_100g', 0)
    cholesterol = nutriments.get('cholesterol_100g', 0)
    energy_kcal = nutriments.get('energy-kcal_100g', 0)
    total_fat = nutriments.get('fat_100g', 0)
    carbohydrates = nutriments.get('carbohydrates_100g', 0)
    fiber = nutriments.get('fiber_100g', 0)
    protein = nutriments.get('proteins_100g', 0)
    monounsaturated_fat = nutriments.get('monounsaturated-fat_100g', 0)
    polyunsaturated_fat = nutriments.get('polyunsaturated-fat_100g', 0)
    calcium = nutriments.get('calcium_100g', 0)
    iron = nutriments.get('iron_100g', 0)
    vitamin_c = nutriments.get('vitamin-c_100g', 0)
    vitamin_d = nutriments.get('vitamin-d_100g', 0)
    vitamin_a = nutriments.get('vitamin-a_100g', 0)
    potassium = nutriments.get('potassium_100g', 0)
    magnesium = nutriments.get('magnesium_100g', 0)
    zinc = nutriments.get('zinc_100g', 0)
    omega_3 = nutriments.get('omega-3-fat_100g', 0)
    omega_6 = nutriments.get('omega-6-fat_100g', 0)
    
    # --- Daily Value (DV) approximations for 100g comparison ---
    DV_SAT_FAT = 0.20  
    DV_SODIUM = 2.30  
    DV_SUGAR_ADD = 0.50
    DV_FIBER = 0.28
    DV_PROTEIN = 0.50
    
    # --- 1. BASELINE SCORE ---
    score = 100 
    
    # --- 2. AGGRESSIVE PENALTIES (Deduction based on %DV and impact) ---
    macro_penalty = 0
    
    # A. SATURATED FAT PENALTY (Max 20 points)
    sat_fat_dv_ratio = sat_fat / DV_SAT_FAT if DV_SAT_FAT > 0 else 0
    macro_penalty += min(20, sat_fat_dv_ratio * 10) 
    
    # B. SODIUM PENALTY (Max 15 points)
    sodium_dv_ratio = sodium / DV_SODIUM if DV_SODIUM > 0 else 0
    macro_penalty += min(15, sodium_dv_ratio * 10)
    
    # C. SUGAR PENALTY (Max 15 points)
    sugar_dv_ratio = sugars / DV_SUGAR_ADD if DV_SUGAR_ADD > 0 else 0
    macro_penalty += min(15, sugar_dv_ratio * 10)
    
    # D. TRANS FAT PENALTY (SEVERE - Max 10 points)
    if trans_fat > 0.001: 
        macro_penalty += 10
    
    # E. CHOLESTEROL & CALORIE DENSITY PENALTY (Max 5 points)
    cholesterol_penalty = min(3, (cholesterol / 0.3) * 5)
    calorie_penalty = min(2, (energy_kcal / 500)) 
    
    macro_penalty += (cholesterol_penalty + calorie_penalty)
    score -= macro_penalty

    # --- 3. BENEFICIAL MACRO BONUSES (Reward up to 30 points total) ---
    macro_bonus = 0
    
    # F. FIBER BONUS (Max 10 points)
    fiber_dv_ratio = fiber / DV_FIBER if DV_FIBER > 0 else 0
    macro_bonus += min(10, fiber_dv_ratio * 10) 
    
    # G. PROTEIN BONUS (Max 10 points)
    protein_dv_ratio = protein / DV_PROTEIN if DV_PROTEIN > 0 else 0
    macro_bonus += min(10, protein_dv_ratio * 10) 
    
    # H. HEALTHY FAT BONUS (Poly/Mono/Omega 3 - Max 5 points)
    healthy_fats_score = monounsaturated_fat + polyunsaturated_fat + omega_3
    macro_bonus += min(5, healthy_fats_score * 0.5) 

    # I. MICRONUTRIENT BONUS (Max 5 points)
    micro_bonus_points = 0
    if calcium > 0.05: micro_bonus_points += 1.5 
    if iron > 0.0005: micro_bonus_points += 1.5
    if vitamin_c > 0.005: micro_bonus_points += 0.5
    if vitamin_a > 0.0005: micro_bonus_points += 0.5
    if potassium > 0.05: micro_bonus_points += 0.5
    if magnesium > 0.01: micro_bonus_points += 0.5

    macro_bonus += min(5, micro_bonus_points)
    score += macro_bonus
    
    # --- 4. CHEMICAL & PROCESSING PENALTY (Risk Weighting) ---
    
    chemical_risk_score = 0
    num_severe_additives = 0
    ingredients_list = product.get('ingredients', [])
    
    for chem in flagged_chemicals:
        cause = chem.get('cause', '').lower()
        avoid = chem.get('avoid', '').lower()
        
        # A. BANNED/CARCINOGENIC RISKS
        if "carcinogen" in cause or "banned" in avoid or "toxic" in avoid:
            chemical_risk_score += 15 
            num_severe_additives += 1
        
        # B. HEALTH/DIGESTIVE RISKS
        elif "hyperactivity" in cause or "gastrointestinal" in cause or "inflammation" in cause:
            chemical_risk_score += 8
            num_severe_additives += 1
        
        # C. MINOR/CAUTION RISKS
        else:
            chemical_risk_score += 4
            
        # Penalty for Quantity/Density 
        chem_name = chem.get('name', '').lower()
        try:
            position = [i for i, item in enumerate(ingredients_list) if item and chem_name in item.get('text', '').lower()][0]
            if position < 3: 
                 chemical_risk_score += 10 
        except IndexError:
            pass

    score -= min(40, chemical_risk_score)
    
    # --- 5. ULTRA-PROCESSING PENALTY (Final Aggressive Check) ---
    if (protein + fiber) < 5 and num_severe_additives >= 3:
        score -= 20 

    # --- 6. FINAL CLAMPING AND HEALTHY CHECK ---
    final_score = int(max(0, min(100, score)))
    
    # Determine Health Status 
    health_status = ""
    if final_score >= 85 and fiber >= 2 and sat_fat <= 5 and sugars <= 5:
        health_status = "💚 Genuinely Healthy"
    elif final_score >= 60:
        health_status = "💙 Good Choice"
    elif final_score < 40:
        health_status = "💔 Warning: Unhealthy"
    else:
        health_status = "💛 Average/Caution"
    
    return final_score, health_status

# --- Layer 3: Dynamic FDA Check Function (remains the same) ---
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


# --- API Endpoint: Data Analysis (remains the same) ---
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


# --- PRODUCTION STATIC FILE ROUTING (The Final Fix) ---

@app.route('/')
def serve_index():
    """Serves the main HTML file when the user visits the root URL."""
    # Flask serves assets from the 'frontend' static folder.
    return app.send_static_file('index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serves all static assets (CSS, JS, etc.) from the frontend directory."""
    # This handles requests for files like 'style.css' or 'script.js' directly.
    return app.send_static_file(filename)