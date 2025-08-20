import re

# Read the file
with open('clinical_note_quality/services/grading_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace instances systematically
# 1. Replace pdqi.average with (pdqi.total/9.0) in calculations
content = re.sub(r'pdqi\.average', '(pdqi.total/9.0)', content)

# 2. Fix the specific instances for display text  
content = content.replace(
    'f"Average Score: {(pdqi.total/9.0):.2f}/5.0"',
    'f"Total Score: {pdqi.total:.0f}/45 (Average: {(pdqi.total/9.0):.2f}/5.0)"'
)

# 3. Update the pdqi_average logging parameter
content = content.replace(
    'pdqi_average=(pdqi.total/9.0),',
    'pdqi_total=pdqi.total,'
)

# 4. Update the legacy return value
content = content.replace(
    "'pdqi_average': result.pdqi.(pdqi.total/9.0),",
    "'pdqi_total': result.pdqi.total,"
)

# Write back the file  
with open('clinical_note_quality/services/grading_service.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated grading_service.py with total scoring')
