import warnings
warnings.warn(
    "'grading.heuristics' is deprecated; use 'clinical_note_quality.services.heuristic_service' instead.",
    DeprecationWarning,
    stacklevel=2,
)
import re
import logging
from typing import Dict, Tuple
from collections import Counter

logger = logging.getLogger(__name__)

def calculate_length_score(text: str) -> float:
    """Calculate length appropriateness score (0-5)."""
    word_count = len(text.split())
    
    if word_count < 50:
        return 1.0  # Too short
    elif word_count < 100:
        return 2.0  # Short but acceptable
    elif word_count <= 500:
        return 5.0  # Optimal range
    elif word_count <= 800:
        return 4.0  # Getting long
    elif word_count <= 1200:
        return 3.0  # Long
    else:
        return 1.0  # Too long

def calculate_redundancy_score(text: str) -> float:
    """Calculate redundancy score based on repeated phrases (0-5)."""
    # Normalize text
    text = re.sub(r'[^\w\s]', '', text.lower())
    words = text.split()
    
    if len(words) < 10:
        return 5.0
    
    # Check for repeated 3-grams
    trigrams = [' '.join(words[i:i+3]) for i in range(len(words)-2)]
    trigram_counts = Counter(trigrams)
    
    # Calculate redundancy ratio
    repeated_trigrams = sum(count - 1 for count in trigram_counts.values() if count > 1)
    total_trigrams = len(trigrams)
    
    if total_trigrams == 0:
        return 5.0
    
    redundancy_ratio = repeated_trigrams / total_trigrams
    
    if redundancy_ratio < 0.05:
        return 5.0  # Very low redundancy
    elif redundancy_ratio < 0.10:
        return 4.0  # Low redundancy
    elif redundancy_ratio < 0.20:
        return 3.0  # Moderate redundancy
    elif redundancy_ratio < 0.30:
        return 2.0  # High redundancy
    else:
        return 1.0  # Very high redundancy

def calculate_structure_score(text: str) -> float:
    """Calculate basic structure score based on formatting (0-5)."""
    lines = text.strip().split('\n')
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    
    # Check for section headers (lines with colons or all caps)
    section_headers = sum(1 for line in non_empty_lines 
                         if ':' in line or (len(line) > 3 and line.isupper()))
    
    # Check for bullet points or numbered lists
    list_items = sum(1 for line in non_empty_lines 
                    if re.match(r'^\s*[-*•]\s+', line) or re.match(r'^\s*\d+\.', line))
    
    # Basic scoring
    score = 3.0  # Base score
    
    if section_headers >= 2:
        score += 1.0  # Good sectioning
    
    if list_items >= 2:
        score += 0.5  # Good use of lists
    
    if len(non_empty_lines) > 1:
        score += 0.5  # Multiple paragraphs/sections
    
    return min(5.0, score)

def analyze_heuristics(clinical_note: str) -> Dict[str, float]:
    """Analyze clinical note using rule-based heuristics."""
    results = {
        'length_score': calculate_length_score(clinical_note),
        'redundancy_score': calculate_redundancy_score(clinical_note),
        'structure_score': calculate_structure_score(clinical_note),
        'word_count': len(clinical_note.split()),
        'character_count': len(clinical_note)
    }
    logger.info("Heuristic analysis completed.")
    return results

def get_heuristic_composite(heuristics: Dict[str, float]) -> float:
    """Calculate composite heuristic score (0-5)."""
    scores = [
        heuristics['length_score'],
        heuristics['redundancy_score'], 
        heuristics['structure_score']
    ]
    return sum(scores) / len(scores) 