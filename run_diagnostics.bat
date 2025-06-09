@echo off
echo Running Clinical Note Quality App diagnostics...

rem Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

rem Check if .env file exists and try to load it
if exist .env (
    echo Found .env file, loading environment variables...
    echo Attempting to read environment variables from .env file...
    
    rem More reliable .env loading for Windows batch files
    for /F "usebackq tokens=*" %%A in (".env") do (
        set "%%A"
    )
) else (
    echo ERROR: .env file not found!
    echo Creating a template .env file for you to fill in...
    (
        echo # Azure OpenAI API Configuration
        echo AZ_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
        echo AZ_OPENAI_KEY=your-api-key-goes-here
        echo AZ_O3_DEPLOYMENT=gpt-o3
    ) > .env
    echo Created .env file. Please edit it with your actual Azure OpenAI credentials.
    echo Then run this script again.
    exit /b 1
)

echo.
echo Current environment settings:
echo AZ_OPENAI_ENDPOINT: %AZ_OPENAI_ENDPOINT%
if "%AZ_OPENAI_ENDPOINT%"=="" echo WARNING: AZ_OPENAI_ENDPOINT is not set!
echo AZ_OPENAI_KEY: [REDACTED for security]
if "%AZ_OPENAI_KEY%"=="" echo WARNING: AZ_OPENAI_KEY is not set!
echo AZ_O3_DEPLOYMENT: %AZ_O3_DEPLOYMENT%
if "%AZ_O3_DEPLOYMENT%"=="" echo WARNING: AZ_O3_DEPLOYMENT is not set (will use default)
echo.

echo Running diagnostic tests...
python diagnose.py

echo.
echo ========================================
echo TROUBLESHOOTING GUIDE:
echo ========================================
echo 1. If you see "Missing credentials" error:
echo    - Edit the .env file with your actual Azure OpenAI credentials
echo    - Make sure your Azure OpenAI service is properly set up
echo.
echo 2. If you see "AuthenticationError":
echo    - Check that your API key is correct
echo    - Check that your endpoint URL is correct
echo.
echo 3. If you see "ResourceNotFound" or "DeploymentNotFound":
echo    - Check that your deployment name (AZ_O3_DEPLOYMENT) is correct
echo    - Make sure you've deployed a model in your Azure OpenAI service
echo.
echo Press any key to exit...
pause >nul

rem Deactivate virtual environment
call venv\Scripts\deactivate.bat
