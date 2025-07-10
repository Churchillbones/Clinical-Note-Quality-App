@echo off
echo Starting Clinical Note Quality Assessment application...

rem Check if virtual environment exists
if not exist venv (
    echo Virtual environment not found. Creating one...
    python -m venv venv
    echo Installing dependencies...
    call venv\Scripts\activate.bat
    pip install --upgrade pip
    pip install -r requirements.txt
) else (
    echo Virtual environment found.
)

rem Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

rem Check if .env file exists and try to load it
if exist .env (
    echo Found .env file, loading environment variables...
    echo Attempting to read environment variables from .env file...
    rem More reliable .env loading for Windows batch files
    for /F "usebackq tokens=* delims=" %%A in (".env") do (
        rem Skip comments and blank lines
        echo %%A | findstr /R "^#" >nul
        if not errorlevel 1 (
            rem This is a comment, skip
        ) else if "%%A"=="" (
            rem This is a blank line, skip
        ) else (
            set "%%A"
        )
    )
) else (
    echo ERROR: .env file not found!
    echo Creating a template .env file for you to fill in...
    echo # Azure OpenAI API Configuration > .env
    echo AZURE_API_KEY=your-api-key-goes-here >> .env
    echo AZURE_ENDPOINT=https://your-resource-name.openai.azure.com/ >> .env
    echo MODEL_NAME=gpt-4o >> .env
    echo API_VERSION=2024-02-15-preview >> .env
    echo AZ_O3_DEPLOYMENT=o3-mini >> .env
    echo AZ_O3_API_VERSION=2025-01-01-preview >> .env
    echo # Model precision: low, medium, or high (default: medium) >> .env
    echo MODEL_PRECISION=medium >> .env
    echo Created .env file. Please edit it with your actual Azure OpenAI credentials.
    echo Then run this script again.
    exit /b 1
)

rem Always verify credentials even if .env file exists
echo Validating Azure OpenAI credentials...
    
rem Check for endpoint (multiple possible names)
if not defined AZ_OPENAI_ENDPOINT if not defined AZURE_ENDPOINT (
    echo ERROR: Azure endpoint not set! Please set AZ_OPENAI_ENDPOINT or AZURE_ENDPOINT in .env file.
    exit /b 1
) else (
    echo Azure endpoint is set.
)

rem Check for API key (multiple possible names)
if not defined AZ_OPENAI_KEY if not defined AZURE_API_KEY (
    echo ERROR: Azure API key not set! Please set AZ_OPENAI_KEY or AZURE_API_KEY in .env file.
    exit /b 1
) else (
    echo Azure API key is set.
)

rem Check for API version
if not defined API_VERSION (
    echo WARNING: API_VERSION not set, will use default (2024-02-15-preview).
) else (
    echo API_VERSION is set to: %API_VERSION%
)

if not defined AZ_O3_DEPLOYMENT (
    echo WARNING: AZ_O3_DEPLOYMENT not set, will use default value from config.
) else (
    echo AZ_O3_DEPLOYMENT is set.
)

echo Would you like to run the application in debug mode? (y/n)
set /p debug_mode=

if /i "%debug_mode%"=="y" (
    echo Setting Flask to debug mode...
    set FLASK_DEBUG=True
    set DEBUG=True
    echo Starting Flask application in DEBUG mode...
    echo Press Ctrl+C to stop the server
    start http://localhost:5000
    python app.py
) else (
    echo Starting Flask application...
    echo Press Ctrl+C to stop the server
    start http://localhost:5000
    python app.py
)

rem No deactivate.bat in standard venv; to deactivate, just close the shell or use 'deactivate' if in an interactive session.
echo Application stopped.
pause
