# CheckTruth - Codebase Documentation

This document explains the technical implementation of the CheckTruth application, focusing on the backend logic (`app.py`) and frontend interactivity (`script.js`).

## 1. Backend: `app.py`

The backend is built with **Flask** and serves as the core intelligence of the application. It handles product data fetching, ingredient analysis, and health scoring.

### Key Components

*   **API Endpoint (`/api/analyze/<barcode>`)**:
    *   Accepts a barcode as a parameter.
    *   Validates the barcode format.
    *   Fetches raw product data from the **Open Food Facts API**.
    *   Analyzes the data and returns a comprehensive JSON response containing the health score, status, warnings, and nutrient breakdown.

*   **Chemical Detection System**:
    *   Loads a database of harmful chemicals from `backend/harmful_chemicals.json`.
    *   Scans the product's `ingredients_text` against this database.
    *   Flags ingredients based on risk levels (High, Medium, Low) and specific health concerns (e.g., "Carcinogen", "Endocrine Disruptor").

*   **Health Scoring Algorithm (`calculate_health_score`)**:
    *   **Base Score**: Starts at 50.
    *   **Penalties**: Deducts points for:
        *   Excessive Sugars (> 30g)
        *   Saturated Fats (> 10g)
        *   Trans Fats (> 0.1g)
        *   High Sodium (> 1.5g)
        *   High Calories
        *   Presence of harmful chemicals (capped penalty).
    *   **Bonuses**: Adds points for:
        *   High Protein (> 10g)
        *   High Fiber (> 8g)
        *   Balanced nutrition profile.
    *   **Auto-Fail Conditions**: Caps the score significantly if critical issues are found (e.g., Trans fats > 0.3g automatically caps score at 20).
 
*   **Disease Warning Engine**:
    *   Generates specific warnings (e.g., "Heart Disease Risk", "Diabetes Risk") based on nutrient thresholds (like high sodium) and specific flagged ingredients.

---

## 2. Frontend: `script.js`

The frontend logic powers the interactive scanner interface (`scan.html`). It manages the camera, user interaction, and data visualization.

### Key Functionalities

*   **Barcode Scanning**:
    *   Utilizes the **ZXing (Zebra Crossing)** library (`ZXing.BrowserMultiFormatReader`) to access the device camera.
    *   Continuously processes the video stream to detect and decode 1D and 2D barcodes.
    *   Handles camera permissions and errors (e.g., "Camera access denied").

*   **API Integration**:
    *   When a barcode is detected, it sends a `GET` request to the backend: `https://checktruth.onrender.com/api/analyze/{barcode}`.
    *   Handles loading states ("Analyzing ingredients...") and error responses (e.g., "Product not found").

*   **Dynamic UI Generation**:
    *   **Chat Interface**: Displays results as "chat bubbles" for a conversational experience.
    *   **Score Header**: Visualizes the health score (0-100) with dynamic colors (Green to Red) and emojis.
    *   **Nutrition Grid**: Renders a readable grid of nutritional values, highlighting concerning amounts (e.g., high sugar in red).
    *   **Ingredient Analysis**:
        *   Lists all ingredients.
        *   **Highlights** identified harmful chemicals with warning badges.
        *   Displays specific health risks and "Avoid if" recommendations for each flagged ingredient.

## Project Structure

```
CheckTruth/
├── app.py                # Main Flask application
├── backend/
│   └── harmful_chemicals.json  # Database of dangerous ingredients
├── frontend/
│   ├── index.html        # Landing page
│   ├── scan.html         # Scanner page
│   ├── script.js         # Scanner logic
│   ├── landing.js        # Landing page interactions
│   └── ...css            # Stylesheets
└── ...
```
