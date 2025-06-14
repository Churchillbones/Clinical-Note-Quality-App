import logging
from flask import Flask, render_template, request, jsonify
from config import Config
from grading.hybrid import grade_note_hybrid
from grading.exceptions import OpenAIServiceError, OpenAIAuthError, OpenAIResponseError

# Initialize Flask application
app = Flask(__name__)

# Load configuration from Config object
app.config.from_object(Config)

# Set up logging
logger = logging.getLogger(__name__)
if not app.debug: # Configure logging for production
    # Example: Log to a file or a logging service
    # For now, basicConfig is fine for development, but use app.logger for Flask context
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
else:
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s: %(message)s')


# Main route - displays the index page
@app.route('/', methods=['GET'])
def index():
    """
    Renders the main page, displaying an error message if provided.
    """
    error = request.args.get('error')
    return render_template('index.html', error=error)

# Route to handle grading via web form
@app.route('/grade', methods=['POST'])
def grade_via_form():
    """
    Handles grading requests submitted through the web form.
    Retrieves the clinical note, calls the grading function,
    and renders the result page or redirects with an error.
    """
    try:
        clinical_note = request.form['clinical_note']
        encounter_transcript = request.form.get('encounter_transcript', '')
        model_precision = request.form.get('model_precision', 'medium')
        
        logger.info(f"Received request for /grade with note: {clinical_note[:100]}..., transcript (present: {bool(encounter_transcript)}), model precision: {model_precision}")
        result = grade_note_hybrid(clinical_note=clinical_note, encounter_transcript=encounter_transcript, model_precision=model_precision)
        logger.info("Successfully returned grading results for /grade.")
        return render_template('result.html', result=result)
    except (OpenAIServiceError, OpenAIAuthError, OpenAIResponseError) as e:
        logger.error(f"OpenAI related error during /grade route processing: {e}", exc_info=True)
        return render_template('index.html', error=str(e))
    except Exception as e:
        logger.error(f"Error during /grade route processing: {e}", exc_info=True)
        return render_template('index.html', error="An unexpected error occurred during grading. Please try again.")

# Route to handle grading via API
@app.route('/api/grade', methods=['POST'])
def grade_via_api():
    """
    Handles grading requests submitted programmatically via the API.
    Expects JSON data with clinical_note and optional encounter_transcript.
    Returns a JSON response with the grading result or an error.
    """
    try:
        data = request.get_json()
        if not data or 'clinical_note' not in data:
            logger.warning("API request for /api/grade missing 'clinical_note'.")
            return jsonify({"error": "clinical_note is required"}), 400
        
        clinical_note = data['clinical_note']
        encounter_transcript = data.get('encounter_transcript', '') # Optional
        model_precision = data.get('model_precision', 'medium') # Optional, default to medium
        
        logger.info(f"Received API request for /api/grade with note: {clinical_note[:100]}..., model precision: {model_precision}")

        result = grade_note_hybrid(clinical_note=clinical_note, encounter_transcript=encounter_transcript, model_precision=model_precision)
        logger.info("Successfully returned API grading results for /api/grade.")
        return jsonify(result)
    except (OpenAIServiceError, OpenAIAuthError, OpenAIResponseError) as e:
        logger.error(f"OpenAI related error during /api/grade route processing: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500 # Or a more specific status code based on error type
    except Exception as e:
        logger.error(f"Error during /api/grade route processing: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred during grading."}), 500

# Standard Flask execution block
if __name__ == '__main__':
    # Use app.run for development, for production a WSGI server like Gunicorn would be used.
    app.run(debug=True, host='0.0.0.0', port=5000)
