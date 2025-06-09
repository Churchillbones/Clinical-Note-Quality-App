# Clinical Note Quality Assessment

A Flask application (`app.py`) that grades clinical notes using the PDQI-9 rubric with Azure OpenAI O3, combined with heuristic analysis and factuality checking.

## Features

- **PDQI-9 Scoring**: Uses Azure OpenAI O3 to score notes across 9 quality dimensions
- **Heuristic Analysis**: Rule-based metrics for length, redundancy, and structure
- **Factuality Checking**: Azure OpenAI O3-based consistency analysis against encounter transcripts (if provided)
- **Hybrid Scoring**: Weighted combination of all assessment methods
- **Model Precision Control**: Choose between low, medium, and high precision settings for the AI model
- **Web Interface**: Clean HTML forms and results display
- **REST API**: JSON endpoints for programmatic access

## Quick Start

### 1. Setup Environment

```bash
# Clone or download the project
cd note-quality-app

# Run setup script (prepares Python virtual environment and installs dependencies)
chmod +x setup.sh
./setup.sh

# Activate virtual environment
source venv/bin/activate
```

### 2. Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your Azure OpenAI credentials
nano .env
```

Required environment variables:
- `AZ_OPENAI_ENDPOINT`: Your Azure OpenAI endpoint URL
- `AZ_OPENAI_KEY`: Your Azure OpenAI API key
- `AZ_O3_DEPLOYMENT`: Your O3 deployment name (e.g., `gpt-o3`, `gpt-4`)
- `AZURE_OPENAI_API_VERSION`: Your Azure OpenAI API version (e.g., `2024-02-15-preview`)

### 3. Run Application

```bash
# Development mode
python app.py

# Production mode with Gunicorn
gunicorn --bind 0.0.0.0:5000 --workers 2 app:app
```

The application will be available at `http://localhost:5000`

## Usage

### Web Interface

1. Navigate to `http://localhost:5000`
2. Enter your clinical note in the "Clinical Note" text area.
3. Optionally, paste the encounter transcript into the "Encounter Transcript" text area for factuality checking.
4. Click "Grade Note" to get a comprehensive assessment.

### REST API

**Endpoint**: `POST /api/grade`

**Request Body**:
```json
{
  "clinical_note": "Patient presents with...",
  "encounter_transcript": "Optional transcript for factuality check"
}
```

**Response**:
```json
{
  "pdqi_scores": {
    "up_to_date": 4,
    "accurate": 4,
    "thorough": 3,
    "useful": 4,
    "organized": 3,
    "concise": 3,
    "consistent": 4,
    "complete": 3,
    "actionable": 4
  },
  "pdqi_average": 3.56,
  "heuristic_analysis": {
    "length_score": 4.0,
    "redundancy_score": 4.5,
    "structure_score": 3.5,
    "composite_score": 4.0,
    "word_count": 245,
    "character_count": 1456
  },
  "factuality_analysis": {
    "consistency_score": 4.0,  # Example score
    "claims_checked": 1        # Will be 0 if no transcript, 1 if transcript provided
  },
  "hybrid_score": 3.67,
  "overall_grade": "B",
  "processing_time_seconds": 2.34
}
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=grading --cov-report=html

# Run specific test file
pytest tests/test_app_routes.py -v
```

## Project Structure 

## PDQI-9 Dimensions

The system evaluates clinical notes across these 9 quality dimensions:

1. **Up-to-date**: Current, evidence-based information
2. **Accurate**: Factually correct medical information  
3. **Thorough**: Comprehensive coverage of relevant details
4. **Useful**: Practical value for clinical decision-making
5. **Organized**: Logical structure and flow
6. **Concise**: Appropriate length without redundancy
7. **Consistent**: Internal consistency and coherence
8. **Complete**: All necessary information included
9. **Actionable**: Clear next steps and recommendations

## Hybrid Scoring

The final score combines three assessment methods:

- **PDQI-9 (70%)**: LLM-based scoring across 9 dimensions
- **Heuristics (20%)**: Rule-based length, redundancy, structure analysis
- **Factuality (10%)**: Azure O3-based consistency checking against transcripts (if provided)

## Development

The application uses the `openai` Python library version 1.x.x for Azure OpenAI integration, ensuring compatibility with the latest SDK features.

### Adding New Features

1. **New Heuristics**: Add functions to `grading/heuristics.py`
2. **Custom Prompts**: Modify `config.py` (PDQI_INSTRUCTIONS, FACTUALITY_INSTRUCTIONS)
3. **UI Changes**: Update templates in `templates/`

### Environment Setup for Development

```bash
# Install development dependencies
pip install pytest pytest-flask pytest-mock pytest-cov black flake8

# Format code
black .

# Lint code  
flake8 grading/ tests/

# Type checking (optional)
pip install mypy
mypy grading/
```

## Troubleshooting

### Common Issues

1. **Azure OpenAI Connection Errors**
   - Verify all Azure OpenAI related environment variables (`AZ_OPENAI_ENDPOINT`, `AZ_OPENAI_KEY`, `AZ_O3_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`) are correctly set in your `.env` file.
   - Check deployment name matches your Azure resource.
   - Ensure sufficient quota for the O3 model.

2. **Missing Environment Variables**
   - Ensure all required environment variables listed above are present in your `.env` file. Missing variables, especially `AZURE_OPENAI_API_VERSION`, can lead to errors.

### Performance Optimization

- **Caching**: Consider Redis for caching O3 responses
- **Async**: Use async Flask for better concurrency
- **Model Optimization**: Use quantized models for faster inference
- **Batch Processing**: Process multiple notes simultaneously

## License

This project is developed for VA clinical documentation quality assessment.

## References

- Stetson et al., *PDQI-9: A Physician Documentation Quality Instrument*, J Biomed Inform 2012
- Human Notes Evaluator (Sultan 2024) - https://huggingface.co/spaces/abachaa/HNE (General reference for note evaluation concepts)
- Croxford et al., *LLM as a Judge for PDQI-9*, 2025 preprint 