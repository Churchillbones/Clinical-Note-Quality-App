"""File-based validation of precision fixes."""

def check_file_fixes():
    print("PRECISION LEVEL FIX VALIDATION")
    print("=" * 40)
    
    success_count = 0
    total_checks = 0
    
    # Check 1: O3Judge precision methods
    try:
        with open("grading/o3_judge.py", "r") as f:
            content = f.read()
        
        checks = [
            ("_get_precision_instructions method", "_get_precision_instructions"),
            ("_build_precision_kwargs method", "_build_precision_kwargs"), 
            ("FAST mode instruction", "MODE: FAST"),
            ("THOROUGH mode instruction", "MODE: THOROUGH"),
            ("BALANCED mode instruction", "MODE: BALANCED"),
            ("Precision logging", "precision:"),
        ]
        
        for check_name, search_term in checks:
            total_checks += 1
            if search_term in content:
                print(f"✓ {check_name}")
                success_count += 1
            else:
                print(f"✗ {check_name}")
                
    except FileNotFoundError:
        print("✗ grading/o3_judge.py not found")
        total_checks += 1
    
    # Check 2: Frontend JavaScript improvements
    try:
        with open("templates/index.html", "r") as f:
            content = f.read()
        
        checks = [
            ("preventDefault() for radio buttons", "preventDefault()"),
            ("Event dispatching", "dispatchEvent"),
            ("Keyboard navigation", "keydown"),
            ("Radio button state management", "checked = false"),
            ("Enhanced click handling", "precision-option"),
        ]
        
        for check_name, search_term in checks:
            total_checks += 1
            if search_term in content:
                print(f"✓ {check_name}")
                success_count += 1
            else:
                print(f"✗ {check_name}")
                
    except FileNotFoundError:
        print("✗ templates/index.html not found")
        total_checks += 5
    
    # Check 3: CSS fixes
    try:
        with open("templates/base.html", "r") as f:
            content = f.read()
        
        checks = [
            ("Precision option CSS", "precision-option"),
            ("User select fix", "user-select: none"),
            ("Cursor pointer", "cursor: pointer"),
            ("Radio button accessibility", "sr-only"),
        ]
        
        for check_name, search_term in checks:
            total_checks += 1
            if search_term in content:
                print(f"✓ {check_name}")
                success_count += 1
            else:
                print(f"✗ {check_name}")
                
    except FileNotFoundError:
        print("✗ templates/base.html not found")
        total_checks += 4
    
    # Check 4: Route debugging
    try:
        with open("clinical_note_quality/http/routes.py", "r") as f:
            content = f.read()
        
        checks = [
            ("Precision debugging logs", "precision selected:"),
            ("Form field debugging", "Available form fields:"),
        ]
        
        for check_name, search_term in checks:
            total_checks += 1
            if search_term in content:
                print(f"✓ {check_name}")
                success_count += 1
            else:
                print(f"✗ {check_name}")
                
    except FileNotFoundError:
        print("✗ clinical_note_quality/http/routes.py not found")
        total_checks += 2
    
    print(f"\nRESULTS: {success_count}/{total_checks} checks passed")
    
    if success_count == total_checks:
        print("🎉 ALL FIXES SUCCESSFULLY APPLIED!")
    elif success_count >= total_checks * 0.8:
        print("✅ Most fixes applied successfully")
    else:
        print("⚠️  Some fixes may be missing")
    
    return success_count, total_checks

if __name__ == "__main__":
    success, total = check_file_fixes()
    
    print("\nEXPECTED BEHAVIOR AFTER FIXES:")
    print("1. All three precision options (Fast/Balanced/Thorough) should be selectable")
    print("2. Each precision level should use different model parameters")
    print("3. 'Balanced' should not behave like 'High Precision' anymore")
    print("4. Radio button selection should work reliably across browsers")
    print("5. Debug logs should show which precision was selected")
