from flask import Flask, request, jsonify
from functools import lru_cache
import requests
import json
import re
import os
import logging
from datetime import datetime, timedelta

# ==================== FLASK INITIALIZATION ====================
app = Flask(__name__, static_folder='frontend', static_url_path='/')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================
class Config:
    """Application configuration constants"""
    HARMFUL_CHEMICALS_PATH = os.path.join(os.path.dirname(__file__), 'backend', 'harmful_chemicals.json')
    OPEN_FOOD_FACTS_API = 'https://world.openfoodfacts.org/api/v0/product'
    FDA_API_URL = 'https://api.fda.gov/food/event.json'
    FDA_TIMEOUT = 5
    CACHE_TIMEOUT = 3600  # 1 hour
    
    # Allowed origins for CORS (add your production domain)
    ALLOWED_ORIGINS = [
        'http://localhost:3000',
        'http://localhost:5000',
        'https://checktruth.onrender.com',
        # Add your production domain here
    ]
    
    # Nutrition thresholds for scoring
    NUTRITION_THRESHOLDS = {
        'sugars': {
            'very_high': {'value': 30, 'penalty': 40},
            'high': {'value': 20, 'penalty': 30},
            'moderate': {'value': 10, 'penalty': 20},
            'low': {'value': 5, 'penalty': 10}
        },
        'saturated_fat': {
            'high': {'value': 10, 'penalty': 20},
            'moderate': {'value': 5, 'penalty': 15},
            'low': {'value': 2, 'penalty': 8}
        },
        'trans_fat': {
            'high': {'value': 0.1, 'penalty': 25},
            'low': {'value': 0.001, 'penalty': 15}
        },
        'sodium': {
            'high': {'value': 1.5, 'penalty': 20},
            'moderate': {'value': 0.8, 'penalty': 15},
            'low': {'value': 0.3, 'penalty': 8}
        },
        'calories': {
            'very_high': {'value': 500, 'penalty': 20},
            'high': {'value': 400, 'penalty': 15},
            'moderate': {'value': 300, 'penalty': 10}
        }
    }

# ==================== CORS CONFIGURATION ====================
@app.after_request
def after_request(response):
    """Add CORS headers with security"""
    origin = request.headers.get('Origin')
    
    # Allow all origins in development, specific origins in production
    if origin in Config.ALLOWED_ORIGINS or app.debug:
        response.headers['Access-Control-Allow-Origin'] = origin or '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Max-Age'] = '3600'
    
    return response

# ==================== DATABASE LOADING ====================
def load_harmful_chemicals():
    """Load harmful chemicals database from JSON file"""
    try:
        with open(Config.HARMFUL_CHEMICALS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            logger.info(f"Loaded {len(data)} harmful chemicals from database")
            return data
    except FileNotFoundError:
        logger.error(f"Harmful chemicals database not found at {Config.HARMFUL_CHEMICALS_PATH}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in harmful chemicals database: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error loading chemicals database: {e}")
        return {}

HARMFUL_CHEMICALS = load_harmful_chemicals()

# ==================== UTILITY FUNCTIONS ====================
def safe_float(value, default=0.0, field_name="unknown"):
    """Safely convert value to float with logging"""
    if value is None:
        return default
    
    try:
        return float(value)
    except (TypeError, ValueError) as e:
        logger.warning(f"Invalid {field_name} value: {value} - {e}")
        return default

def validate_barcode(barcode):
    """Validate barcode format"""
    if not barcode:
        return False, "Barcode is required"
    
    # Remove any whitespace
    barcode = str(barcode).strip()
    
    # Check if it's numeric and reasonable length (8-14 digits)
    if not barcode.isdigit():
        return False, "Barcode must contain only digits"
    
    if len(barcode) < 8 or len(barcode) > 14:
        return False, "Barcode must be between 8 and 14 digits"
    
    return True, barcode

# ==================== NUTRITION EXTRACTION ====================
def extract_nutrition_facts(product):
    """Extract comprehensive nutrition facts from product data"""
    nutriments = product.get('nutriments', {})
    
    nutrition = {
        'calories': safe_float(nutriments.get('energy-kcal_100g'), field_name='calories'),
        'protein': safe_float(nutriments.get('proteins_100g'), field_name='protein'),
        'carbohydrates': safe_float(nutriments.get('carbohydrates_100g'), field_name='carbohydrates'),
        'sugars': safe_float(nutriments.get('sugars_100g'), field_name='sugars'),
        'added_sugars': safe_float(nutriments.get('added-sugars_100g'), field_name='added_sugars'),
        'fiber': safe_float(nutriments.get('fiber_100g'), field_name='fiber'),
        'fat': safe_float(nutriments.get('fat_100g'), field_name='fat'),
        'saturated_fat': safe_float(nutriments.get('saturated-fat_100g'), field_name='saturated_fat'),
        'trans_fat': safe_float(nutriments.get('trans-fat_100g'), field_name='trans_fat'),
        'cholesterol': safe_float(nutriments.get('cholesterol_100g'), field_name='cholesterol'),
        'sodium': safe_float(nutriments.get('sodium_100g'), field_name='sodium'),
        'potassium': safe_float(nutriments.get('potassium_100g'), field_name='potassium'),
        'calcium': safe_float(nutriments.get('calcium_100g'), field_name='calcium'),
        'iron': safe_float(nutriments.get('iron_100g'), field_name='iron'),
        'vitamin_c': safe_float(nutriments.get('vitamin-c_100g'), field_name='vitamin_c')
    }
    
    return nutrition

# ==================== CHEMICAL DETECTION ====================
def detect_harmful_chemicals(ingredients_text):
    """Detect harmful chemicals in ingredient list"""
    if not ingredients_text or not isinstance(ingredients_text, str):
        return []
    
    flagged = []
    ingredients_lower = ingredients_text.lower()
    
    for chemical_name, details in HARMFUL_CHEMICALS.items():
        if not isinstance(details, dict):
            continue
        
        # Check if chemical name appears in ingredients
        if chemical_name.lower() in ingredients_lower:
            flagged_item = {
                'name': chemical_name,
                'cause': details.get('cause', 'Unknown health concern'),
                'avoid': details.get('avoid', 'General population'),
                'risk_level': details.get('risk_level', 'medium'),
                'macros': details.get('macros', {})
            }
            flagged.append(flagged_item)
            logger.info(f"Flagged chemical detected: {chemical_name}")
    
    return flagged

# ==================== DISEASE WARNING GENERATION ====================
def generate_disease_warnings(flagged_chemicals, nutrition_facts):
    """Generate disease warnings based on flagged chemicals and nutrition"""
    warnings = set()
    
    # Warnings from chemicals
    for chemical in flagged_chemicals:
        cause = chemical.get('cause', '').lower()
        
        if 'cancer' in cause or 'carcinogen' in cause:
            warnings.add('Cancer Risk')
        if 'diabetes' in cause or 'blood sugar' in cause:
            warnings.add('Diabetes Risk')
        if 'heart' in cause or 'cardiovascular' in cause:
            warnings.add('Heart Disease')
        if 'obesity' in cause or 'weight gain' in cause:
            warnings.add('Obesity Risk')
        if 'allerg' in cause:
            warnings.add('Allergic Reactions')
        if 'kidney' in cause:
            warnings.add('Kidney Issues')
        if 'liver' in cause:
            warnings.add('Liver Damage')
    
    # Warnings from nutrition
    if nutrition_facts.get('trans_fat', 0) > 0.1:
        warnings.add('Heart Disease')
    
    if nutrition_facts.get('sugars', 0) > 25:
        warnings.add('Diabetes Risk')
        warnings.add('Obesity Risk')
    
    if nutrition_facts.get('sodium', 0) > 1500:
        warnings.add('High Blood Pressure')
        warnings.add('Heart Disease')
    
    if nutrition_facts.get('saturated_fat', 0) > 10:
        warnings.add('High Cholesterol')
        warnings.add('Heart Disease')
    
    return sorted(list(warnings))

# ==================== HEALTH SCORE CALCULATION ====================
def calculate_health_score(nutrition_facts, flagged_chemicals):
    """
    Calculate comprehensive health score using nutrition and chemical data
    Returns: (score: int, status: str)
    """
    penalties = []
    bonuses = []
    
    # Extract nutrition values
    sugars = nutrition_facts.get('sugars', 0)
    sat_fat = nutrition_facts.get('saturated_fat', 0)
    trans_fat = nutrition_facts.get('trans_fat', 0)
    sodium = nutrition_facts.get('sodium', 0) / 1000  # Convert mg to g
    calories = nutrition_facts.get('calories', 0)
    protein = nutrition_facts.get('protein', 0)
    fiber = nutrition_facts.get('fiber', 0)
    fat = nutrition_facts.get('fat', 0)
    
    # ==================== PENALTIES ====================
    
    # Sugar penalties
    sugar_thresholds = Config.NUTRITION_THRESHOLDS['sugars']
    if sugars > sugar_thresholds['very_high']['value']:
        penalties.append(sugar_thresholds['very_high']['penalty'])
    elif sugars > sugar_thresholds['high']['value']:
        penalties.append(sugar_thresholds['high']['penalty'])
    elif sugars > sugar_thresholds['moderate']['value']:
        penalties.append(sugar_thresholds['moderate']['penalty'])
    elif sugars > sugar_thresholds['low']['value']:
        penalties.append(sugar_thresholds['low']['penalty'])
    
    # Saturated fat penalties
    sat_fat_thresholds = Config.NUTRITION_THRESHOLDS['saturated_fat']
    if sat_fat > sat_fat_thresholds['high']['value']:
        penalties.append(sat_fat_thresholds['high']['penalty'])
    elif sat_fat > sat_fat_thresholds['moderate']['value']:
        penalties.append(sat_fat_thresholds['moderate']['penalty'])
    elif sat_fat > sat_fat_thresholds['low']['value']:
        penalties.append(sat_fat_thresholds['low']['penalty'])
    
    # Trans fat penalties (zero tolerance)
    trans_fat_thresholds = Config.NUTRITION_THRESHOLDS['trans_fat']
    if trans_fat > trans_fat_thresholds['high']['value']:
        penalties.append(trans_fat_thresholds['high']['penalty'])
    elif trans_fat > trans_fat_thresholds['low']['value']:
        penalties.append(trans_fat_thresholds['low']['penalty'])
    
    # Sodium penalties
    sodium_thresholds = Config.NUTRITION_THRESHOLDS['sodium']
    if sodium > sodium_thresholds['high']['value']:
        penalties.append(sodium_thresholds['high']['penalty'])
    elif sodium > sodium_thresholds['moderate']['value']:
        penalties.append(sodium_thresholds['moderate']['penalty'])
    elif sodium > sodium_thresholds['low']['value']:
        penalties.append(sodium_thresholds['low']['penalty'])
    
    # Calorie penalties
    calorie_thresholds = Config.NUTRITION_THRESHOLDS['calories']
    if calories > calorie_thresholds['very_high']['value']:
        penalties.append(calorie_thresholds['very_high']['penalty'])
    elif calories > calorie_thresholds['high']['value']:
        penalties.append(calorie_thresholds['high']['penalty'])
    elif calories > calorie_thresholds['moderate']['value']:
        penalties.append(calorie_thresholds['moderate']['penalty'])
    
    # ==================== BONUSES ====================
    
    # Protein bonuses
    if protein > 10:
        bonuses.append(15)
    elif protein > 6:
        bonuses.append(10)
    elif protein > 3:
        bonuses.append(5)
    
    # Fiber bonuses
    if fiber > 8:
        bonuses.append(20)
    elif fiber > 5:
        bonuses.append(15)
    elif fiber > 3:
        bonuses.append(8)
    elif fiber > 1:
        bonuses.append(3)
    
    # Balanced nutrition bonus
    if (4 < protein < 15 and 2 < fiber < 10 and 
        sugars < 10 and sat_fat < 3):
        bonuses.append(10)
    
    # ==================== CHEMICAL PENALTIES ====================
    
    chemical_penalty = 0
    for chem in flagged_chemicals:
        risk_level = chem.get('risk_level', 'medium')
        
        if risk_level == 'high':
            chemical_penalty += 15
        elif risk_level == 'medium':
            chemical_penalty += 10
        else:
            chemical_penalty += 5
        
        # Additional penalties based on chemical macros
        macros = chem.get('macros', {})
        if macros.get('sugars_per_100g', 0) > 50:
            chemical_penalty += 5
        if macros.get('saturated_fat_per_100g', 0) > 20:
            chemical_penalty += 5
        if macros.get('trans_fat_per_100g', 0) > 0.1:
            chemical_penalty += 10
        if macros.get('sodium_per_100g', 0) > 1000:
            chemical_penalty += 3
    
    # Cap chemical penalty
    chemical_penalty = min(40, chemical_penalty)
    penalties.append(chemical_penalty)
    
    # ==================== CALCULATE FINAL SCORE ====================
    
    base_score = 50
    total_bonuses = sum(bonuses)
    total_penalties = sum(penalties)
    
    score = base_score + total_bonuses - total_penalties
    
    # ==================== AUTO-FAIL CONDITIONS ====================
    
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
    
    # Clamp score between 0 and 100
    score = max(0, min(100, int(score)))
    
    # ==================== DETERMINE STATUS ====================
    
    # Special condition checks first
    if trans_fat > 0.001:
        status = "🚫 Contains Trans Fats"
    elif sugars > 20 and protein < 5:
        status = "⚠️ High Sugar Warning"
    elif score >= 85:
        status = "💚 Excellent Choice"
    elif score >= 70:
        status = "💙 Good Choice"
    elif score >= 50:
        status = "💛 Average"
    elif score >= 35:
        status = "🧡 Unhealthy"
    else:
        status = "💔 Very Unhealthy"
    
    logger.info(f"Health score calculated: {score} ({status})")
    logger.info(f"Bonuses: {total_bonuses}, Penalties: {total_penalties}")
    
    return score, status

# ==================== FDA API INTEGRATION ====================
@lru_cache(maxsize=500)
def check_fda_adverse_events(ingredient_name):
    """
    Query FDA API for adverse event reports
    Returns: (has_reports: bool, message: str)
    """
    if not ingredient_name or not isinstance(ingredient_name, str):
        return False, ""
    
    # Clean ingredient name
    clean_name = re.sub(r'[^a-z\s]', '', ingredient_name.lower()).strip()
    if not clean_name:
        return False, ""
    
    search_term = clean_name.replace(" ", "+")
    
    query = {
        'search': f'products.ingredient.exact:{search_term}',
        'limit': 1
    }
    
    try:
        response = requests.get(
            Config.FDA_API_URL, 
            params=query, 
            timeout=Config.FDA_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        
        total_reports = data.get('meta', {}).get('results', {}).get('total', 0)
        
        if total_reports > 0:
            logger.info(f"FDA reports found for {ingredient_name}: {total_reports}")
            return True, f"FDA Adverse Event Reports: {total_reports}"
        else:
            return False, ""
            
    except requests.exceptions.Timeout:
        logger.warning(f"FDA API timeout for ingredient: {ingredient_name}")
        return False, "FDA API timeout"
    except requests.exceptions.RequestException as e:
        logger.error(f"FDA API error for {ingredient_name}: {e}")
        return False, f"FDA API error: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error checking FDA for {ingredient_name}: {e}")
        return False, ""

# ==================== OPEN FOOD FACTS API ====================
@lru_cache(maxsize=1000)
def fetch_product_from_openfoodfacts(barcode):
    """
    Fetch product data from Open Food Facts API
    Returns: product dict or None
    """
    try:
        url = f"{Config.OPEN_FOOD_FACTS_API}/{barcode}.json"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('status') == 1:
            logger.info(f"Product found for barcode: {barcode}")
            return data.get('product')
        else:
            logger.warning(f"Product not found for barcode: {barcode}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching product {barcode}: {e}")
        return None

# ==================== MAIN API ENDPOINT ====================
@app.route('/api/analyze/<barcode>', methods=['GET'])
def analyze_product(barcode):
    """
    Main API endpoint to analyze a product by barcode
    """
    # Validate barcode
    is_valid, result = validate_barcode(barcode)
    if not is_valid:
        return jsonify({
            'status': 'error',
            'message': result
        }), 400
    
    barcode = result  # Use cleaned barcode
    
    # Fetch product data
    product = fetch_product_from_openfoodfacts(barcode)
    
    if not product:
        return jsonify({
            'status': 'error',
            'message': 'Product not found in Open Food Facts database. Try another barcode.'
        }), 404
    
    # Extract data
    product_name = product.get('product_name', 'Unknown Product')
    ingredients_text = product.get('ingredients_text', '')
    
    # Detect harmful chemicals
    flagged_chemicals = detect_harmful_chemicals(ingredients_text)
    
    # Extract nutrition facts
    nutrition_facts = extract_nutrition_facts(product)
    
    # Calculate health score
    health_score, health_status = calculate_health_score(nutrition_facts, flagged_chemicals)
    
    # Generate disease warnings
    disease_warnings = generate_disease_warnings(flagged_chemicals, nutrition_facts)
    
    # Build response
    response_data = {
        'status': 'success',
        'barcode': barcode,
        'product_name': product_name,
        'health_score': health_score,
        'health_status': health_status,
        'ingredients_text': ingredients_text,
        'flagged_chemicals': flagged_chemicals,
        'disease_warnings': disease_warnings,
        'nutrition_facts': nutrition_facts,
        'analyzed_at': datetime.now().isoformat()
    }
    
    logger.info(f"Successfully analyzed product: {product_name} (Score: {health_score})")
    
    return jsonify(response_data), 200

# ==================== HEALTH CHECK ENDPOINT ====================
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'chemicals_loaded': len(HARMFUL_CHEMICALS),
        'timestamp': datetime.now().isoformat()
    }), 200

# ==================== SERVE FRONTEND ====================
@app.route('/')
def serve_frontend():
    """Serve the main frontend page"""
    return app.send_static_file('index.html')

# ==================== ERROR HANDLERS ====================
@app.errorhandler(404)
def not_found(e):
    return jsonify({
        'status': 'error',
        'message': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal server error: {e}")
    return jsonify({
        'status': 'error',
        'message': 'Internal server error'
    }), 500

# ==================== RUN APPLICATION ====================
if __name__ == '__main__':
    # Development server
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=os.environ.get('FLASK_ENV') == 'development'
    )