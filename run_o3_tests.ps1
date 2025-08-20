#!/usr/bin/env pwsh
# PowerShell script to run O3 model tests

Write-Host "===================================" -ForegroundColor Green
Write-Host "Running O3 Model API Tests" -ForegroundColor Green
Write-Host "===================================" -ForegroundColor Green

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python version: $pythonVersion" -ForegroundColor Blue
} catch {
    Write-Host "❌ Python not found in PATH" -ForegroundColor Red
    exit 1
}

# Check if required modules are available
Write-Host "`nChecking required modules..." -ForegroundColor Blue
$requiredModules = @("openai", "config")
foreach ($module in $requiredModules) {
    try {
        python -c "import $module; print('✅ $module available')" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ Module '$module' not available" -ForegroundColor Red
        }
    } catch {
        Write-Host "❌ Module '$module' not available" -ForegroundColor Red
    }
}

Write-Host "`n" + "="*50 -ForegroundColor Yellow
Write-Host "Test 1: Basic O3 API Connection" -ForegroundColor Yellow
Write-Host "="*50 -ForegroundColor Yellow

try {
    python test_o3_api_simple.py
    $test1Success = $LASTEXITCODE -eq 0
} catch {
    Write-Host "❌ Test 1 failed to execute" -ForegroundColor Red
    $test1Success = $false
}

Write-Host "`n" + "="*50 -ForegroundColor Yellow
Write-Host "Test 2: O3 PDQI Service" -ForegroundColor Yellow
Write-Host "="*50 -ForegroundColor Yellow

try {
    python test_o3_service.py
    $test2Success = $LASTEXITCODE -eq 0
} catch {
    Write-Host "❌ Test 2 failed to execute" -ForegroundColor Red
    $test2Success = $false
}

# Summary
Write-Host "`n" + "="*50 -ForegroundColor Green
Write-Host "TEST SUMMARY" -ForegroundColor Green
Write-Host "="*50 -ForegroundColor Green

if ($test1Success) {
    Write-Host "✅ Basic O3 API Test: PASSED" -ForegroundColor Green
} else {
    Write-Host "❌ Basic O3 API Test: FAILED" -ForegroundColor Red
}

if ($test2Success) {
    Write-Host "✅ O3 PDQI Service Test: PASSED" -ForegroundColor Green
} else {
    Write-Host "❌ O3 PDQI Service Test: FAILED" -ForegroundColor Red
}

if ($test1Success -or $test2Success) {
    Write-Host "`n🎉 At least one test passed - O3 model is accessible!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "`n💥 All tests failed - check your O3 configuration" -ForegroundColor Red
    Write-Host "Check the following:" -ForegroundColor Yellow
    Write-Host "  - Azure OpenAI endpoint is correct" -ForegroundColor Yellow
    Write-Host "  - Azure OpenAI API key is valid" -ForegroundColor Yellow
    Write-Host "  - O3 deployment name is correct" -ForegroundColor Yellow
    Write-Host "  - O3 API version (2025-04-01-preview) is supported" -ForegroundColor Yellow
    exit 1
}
