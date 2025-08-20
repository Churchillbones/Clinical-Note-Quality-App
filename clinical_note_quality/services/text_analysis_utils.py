"""
Common utilities for embedding-based detection services.
Extracts shared functionality between ContradictionDetector and HallucinationDetector.

Following Claude.md principles:
- DRY: Don't Repeat Yourself - common patterns extracted
- Clean Architecture: Pure functions with no side effects
- Single Responsibility: Each function has one clear purpose
"""
from __future__ import annotations

import re
from typing import List, Set, Dict, Optional
from enum import Enum

from clinical_note_quality.domain.semantic_models import MedicalCategory


class TextAnalyzer:
    """Utility class for analyzing medical text content."""

    # Medical terminology patterns for categorization
    MEDICAL_PATTERNS = {
        MedicalCategory.MEDICATION: [
            r'\b\d+\s*(mg|ml|mcg|units|g|tablet|capsule|pill)\b',
            r'\b(prescribed|administered|given|medication|drug|pill|dose)\b',
            r'\b\w*(cillin|azole|pril|statin|zole)\b',  # Common drug suffixes
        ],
        MedicalCategory.ALLERGY: [
            r'\b(allergic|allergy|reaction|anaphylaxis)\b',
            r'\b(rash|hives|swelling|itching)\b',
        ],
        MedicalCategory.DIAGNOSIS: [
            r'\b(diagnosed|diagnosis|condition|disease|disorder)\b',
            r'\b(diabetes|hypertension|asthma|copd|pneumonia)\b',
        ],
        MedicalCategory.PROCEDURE: [
            r'\b(procedure|surgery|performed|operation|surgical)\b',
            r'\b(x-ray|mri|ct|scan|ultrasound|biopsy)\b',
        ],
        MedicalCategory.VITAL_SIGNS: [
            r'\b(blood pressure|bp)\s*\d+/\d+\b',
            r'\b(heart rate|hr|pulse)\s*\d+\b',
            r'\b(temperature|temp)\s*\d+\b',
            r'\b(respiratory rate|rr)\s*\d+\b',
            r'\b(oxygen saturation|o2 sat)\s*\d+\b',
        ],
        MedicalCategory.LAB_RESULT: [
            r'\b(lab|laboratory|test|blood work|result)\b',
            r'\b(glucose|cholesterol|hemoglobin|creatinine)\b',
            r'\b(positive|negative|elevated|decreased|normal)\b',
        ],
        MedicalCategory.SYMPTOM: [
            r'\b(pain|symptom|complaint|discomfort)\b',
            r'\b(reports|denies|admits|states|mentions)\b',
            r'\b(nausea|fever|headache|fatigue|weakness)\b',
        ],
        MedicalCategory.FOLLOW_UP: [
            r'\b(follow|return|appointment|visit|recheck)\b',
            r'\b(weeks?|months?|days?)\b',
        ],
        MedicalCategory.SOCIAL_HISTORY: [
            r'\b(smoking|alcohol|drinks|tobacco|social)\b',
            r'\b(drinks per|packs per|cigarettes|beer|wine)\b',
        ],
        MedicalCategory.FAMILY_HISTORY: [
            r'\b(family|father|mother|parent|sibling|history)\b',
            r'\b(hereditary|genetic|familial)\b',
        ],
    }

    # Common negation patterns
    NEGATION_PATTERNS = [
        r'\b(no|denies|negative|absent|without|never|not)\b',
        r'\b(no evidence of|no signs of|no history of)\b',
    ]

    # Common affirmative patterns
    AFFIRMATIVE_PATTERNS = [
        r'\b(positive|present|has|reports|admits|confirms|yes)\b',
        r'\b(evidence of|signs of|history of)\b',
    ]

    # Temporal patterns
    TEMPORAL_PATTERNS = {
        'morning': [r'\b(morning|am|a\.?m\.?)\b'],
        'afternoon': [r'\b(afternoon|pm|p\.?m\.?)\b'],
        'evening': [r'\b(evening|night)\b'],
        'daily': [r'\b(daily|once daily|per day|qd)\b'],
        'weekly': [r'\b(weekly|once weekly|per week)\b'],
        'monthly': [r'\b(monthly|once monthly|per month)\b'],
        'hourly': [r'\b(hourly|every hour|per hour)\b'],
        'bid': [r'\b(twice daily|bid|b\.i\.d\.)\b'],
        'tid': [r'\b(three times daily|tid|t\.i\.d\.)\b'],
        'qid': [r'\b(four times daily|qid|q\.i\.d\.)\b'],
    }

    @staticmethod
    def extract_sentences(text: str, min_length: int = 10) -> List[str]:
        """Extract meaningful sentences from text."""
        sentences = []
        
        # Split on periods, but be careful with abbreviations
        parts = re.split(r'\.(?!\s*\d)|[!?]', text)
        
        for part in parts:
            sentence = part.strip()
            if len(sentence) >= min_length:
                sentences.append(sentence)
        
        return sentences

    @staticmethod
    def categorize_medical_content(text: str) -> MedicalCategory:
        """Categorize medical content into appropriate category."""
        text_lower = text.lower()
        
        # Score each category based on pattern matches
        category_scores = {}
        
        for category, patterns in TextAnalyzer.MEDICAL_PATTERNS.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower))
                score += matches
            
            if score > 0:
                category_scores[category] = score
        
        # Return category with highest score, or DIAGNOSIS as default
        if category_scores:
            return max(category_scores.items(), key=lambda x: x[1])[0]
        else:
            return MedicalCategory.DIAGNOSIS

    @staticmethod
    def extract_numerical_values(text: str) -> List[Dict[str, str]]:
        """Extract numerical values with units from text."""
        # Pattern for number + optional unit
        pattern = r'(\d+(?:\.\d+)?)\s*(mg|ml|mcg|units|mmhg|bpm|°f|°c|degrees|/min|%|lbs|kg|g)?'
        
        matches = re.findall(pattern, text.lower())
        
        values = []
        for number, unit in matches:
            values.append({
                'number': number,
                'unit': unit or 'none',
                'full_match': f"{number}{unit}" if unit else number
            })
        
        return values

    @staticmethod
    def extract_blood_pressure(text: str) -> List[str]:
        """Extract blood pressure readings."""
        pattern = r'(\d{2,3}/\d{2,3})\s*(?:mmhg)?'
        return re.findall(pattern, text.lower())

    @staticmethod
    def has_negation(text: str) -> bool:
        """Check if text contains negation patterns."""
        text_lower = text.lower()
        return any(
            re.search(pattern, text_lower) 
            for pattern in TextAnalyzer.NEGATION_PATTERNS
        )

    @staticmethod
    def has_affirmation(text: str) -> bool:
        """Check if text contains affirmative patterns."""
        text_lower = text.lower()
        return any(
            re.search(pattern, text_lower) 
            for pattern in TextAnalyzer.AFFIRMATIVE_PATTERNS
        )

    @staticmethod
    def extract_temporal_indicators(text: str) -> Set[str]:
        """Extract temporal indicators from text."""
        text_lower = text.lower()
        temporal_categories = set()
        
        for category, patterns in TextAnalyzer.TEMPORAL_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    temporal_categories.add(category)
        
        return temporal_categories

    @staticmethod
    def is_factual_claim(text: str, min_length: int = 15) -> bool:
        """Determine if text contains specific, verifiable factual claims."""
        if len(text.strip()) < min_length:
            return False
        
        # Must contain at least one factual pattern
        factual_indicators = [
            r'\d+\s*(mg|ml|mcg|units|g|kg|lbs|°f|°c|mmhg|bpm)',  # Measurements
            r'\b(prescribed|administered|given|ordered|performed)\b',  # Actions
            r'\b(diagnosed with|allergy to|history of)\b',  # Specific medical facts
            r'\b(patient (reports|states|denies|admits))\b',  # Patient statements
            r'\bblood pressure.*\d+/\d+\b',  # Specific vital signs
        ]
        
        text_lower = text.lower()
        
        # Check for factual indicators
        has_factual_indicator = any(
            re.search(pattern, text_lower) 
            for pattern in factual_indicators
        )
        
        if not has_factual_indicator:
            return False
        
        # Exclude vague statements
        vague_indicators = [
            r'\b(seems|appears|might|possibly|maybe|probably)\b',
            r'\b(somewhat|rather|quite|very)\b',
            r'\b(will consider|plan to|thinking about)\b',
        ]
        
        is_vague = any(
            re.search(pattern, text_lower) 
            for pattern in vague_indicators
        )
        
        return not is_vague

    @staticmethod
    def extract_medical_terms(text: str) -> Set[str]:
        """Extract key medical terms from text."""
        terms = set()
        text_lower = text.lower()
        
        # Common medical term patterns
        medical_term_patterns = [
            r'\b\w*azole\b',   # Antifungals
            r'\b\w*cillin\b',  # Antibiotics  
            r'\b\w*pril\b',    # ACE inhibitors
            r'\b\w*statin\b',  # Statins
            r'\b\w*zole\b',    # PPIs
            r'\bdiabetes\b',
            r'\bhypertension\b',
            r'\ballergy\b',
            r'\bpain\b',
            r'\bfever\b',
            r'\bnausea\b',
            r'\bheadache\b',
        ]
        
        for pattern in medical_term_patterns:
            matches = re.findall(pattern, text_lower)
            terms.update(matches)
        
        return terms


class SimilarityAnalyzer:
    """Utility class for analyzing similarity and detecting patterns."""

    @staticmethod
    def is_in_similarity_range(similarity: float, range_tuple: tuple) -> bool:
        """Check if similarity is within specified range."""
        return range_tuple[0] <= similarity <= range_tuple[1]

    @staticmethod
    def calculate_confidence_from_similarity(similarity: float) -> float:
        """Convert similarity score to confidence score (inverse relationship)."""
        return max(0.0, min(1.0, 1.0 - similarity))

    @staticmethod
    def find_best_matches(similarities: List[float], threshold: float = 0.5) -> List[int]:
        """Find indices of similarities above threshold, sorted by score."""
        matches = [
            (i, score) for i, score in enumerate(similarities) 
            if score >= threshold
        ]
        
        # Sort by similarity score descending
        matches.sort(key=lambda x: x[1], reverse=True)
        
        return [i for i, _ in matches]

    @staticmethod  
    def has_temporal_conflict(temporal_set1: Set[str], temporal_set2: Set[str]) -> bool:
        """Check for conflicting temporal indicators between two sets."""
        
        # Define mutually exclusive temporal categories
        conflicts = [
            ({'morning'}, {'afternoon', 'evening'}),
            ({'daily'}, {'weekly', 'monthly'}),
            ({'hourly'}, {'daily', 'weekly'}),
            ({'bid'}, {'daily', 'tid', 'qid'}),
            ({'tid'}, {'daily', 'bid', 'qid'}),
            ({'qid'}, {'daily', 'bid', 'tid'}),
        ]
        
        for set_a, set_b in conflicts:
            if (temporal_set1 & set_a and temporal_set2 & set_b) or \
               (temporal_set1 & set_b and temporal_set2 & set_a):
                return True
        
        return False


class MedicalSeverityCalculator:
    """Utility class for calculating medical severity scores."""

    # Severity weights for different medical categories
    CATEGORY_WEIGHTS = {
        MedicalCategory.MEDICATION: 0.95,       # Highest - dosage errors critical
        MedicalCategory.ALLERGY: 0.95,          # Highest - allergy conflicts dangerous  
        MedicalCategory.DIAGNOSIS: 0.90,        # Very high - diagnostic accuracy crucial
        MedicalCategory.PROCEDURE: 0.85,        # High - procedure accuracy important
        MedicalCategory.VITAL_SIGNS: 0.80,      # High - vital sign accuracy important
        MedicalCategory.LAB_RESULT: 0.75,       # Medium-high - lab accuracy important
        MedicalCategory.SYMPTOM: 0.70,          # Medium - symptom reporting varies
        MedicalCategory.FOLLOW_UP: 0.60,        # Medium-low - timing flexible
        MedicalCategory.SOCIAL_HISTORY: 0.50,   # Lower - less immediately critical
        MedicalCategory.FAMILY_HISTORY: 0.45,   # Lower - less immediately critical
    }

    @classmethod
    def calculate_base_severity(cls, medical_category: MedicalCategory) -> float:
        """Get base severity for medical category."""
        return cls.CATEGORY_WEIGHTS.get(medical_category, 0.5)

    @classmethod
    def adjust_severity_for_detection_type(
        cls, 
        base_severity: float, 
        detection_type: str,
        confidence: float = 1.0
    ) -> float:
        """Adjust severity based on type of detection and confidence."""
        
        # Multipliers for different types of detection
        type_multipliers = {
            'numerical': 1.0,    # Numerical conflicts most serious
            'negation': 0.9,     # Presence/absence conflicts serious
            'temporal': 0.7,     # Timing issues less critical
            'factual': 0.8,      # Other factual conflicts moderately serious
            'hallucination': 0.85,  # Hallucinations quite serious
        }
        
        multiplier = type_multipliers.get(detection_type, 0.8)
        adjusted_severity = base_severity * multiplier * confidence
        
        # Clamp to valid range
        return max(0.0, min(1.0, adjusted_severity))
