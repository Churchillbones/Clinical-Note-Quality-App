@echo off
echo ===================================
echo Running O3 Model API Tests
echo ===================================

echo.
echo Testing basic O3 API connection...
python test_o3_api_simple.py

echo.
echo.
echo Testing O3 through PDQI service...
python test_o3_service.py

echo.
echo ===================================
echo All tests completed
echo ===================================
pause
