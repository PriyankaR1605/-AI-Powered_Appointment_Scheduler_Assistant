"""
Department normalization dictionary mapping informal, slang, or clinical terms
to standard, canonical medical department names.
"""

from typing import Optional

CANONICAL_DEPARTMENTS = {
    # Dentistry
    "dentist": "Dentistry",
    "dental": "Dentistry",
    "teeth": "Dentistry",
    "tooth": "Dentistry",
    "orthodontist": "Dentistry",
    "orthodontics": "Dentistry",
    "periodontist": "Dentistry",
    "dentistry": "Dentistry",

    # Cardiology
    "heart": "Cardiology",
    "cardio": "Cardiology",
    "cardiologist": "Cardiology",
    "cardiology": "Cardiology",

    # Ophthalmology
    "eye": "Ophthalmology",
    "eyes": "Ophthalmology",
    "eye doctor": "Ophthalmology",
    "optometrist": "Ophthalmology",
    "ophthalmologist": "Ophthalmology",
    "ophthalmology": "Ophthalmology",

    # Dermatology
    "skin": "Dermatology",
    "dermatologist": "Dermatology",
    "dermatology": "Dermatology",
    "derma": "Dermatology",

    # General Medicine
    "general": "General Medicine",
    "general physician": "General Medicine",
    "general medicine": "General Medicine",
    "gp": "General Medicine",
    "physician": "General Medicine",
    "family doctor": "General Medicine",
    "doctor": "General Medicine",

    # Orthopedics
    "bone": "Orthopedics",
    "bones": "Orthopedics",
    "ortho": "Orthopedics",
    "orthopedic": "Orthopedics",
    "orthopedics": "Orthopedics",
    "joint": "Orthopedics",

    # Neurology
    "neuro": "Neurology",
    "neurologist": "Neurology",
    "neurology": "Neurology",
    "brain": "Neurology",

    # ENT (Ear, Nose, Throat)
    "ent": "Otolaryngology (ENT)",
    "ear": "Otolaryngology (ENT)",
    "throat": "Otolaryngology (ENT)",
    "otolaryngology": "Otolaryngology (ENT)",

    # Pediatrics
    "pediatric": "Pediatrics",
    "pediatrics": "Pediatrics",
    "pediatrician": "Pediatrics",
    "child doctor": "Pediatrics",
    "kids": "Pediatrics",

    # Psychiatry & Mental Health
    "psychiatry": "Psychiatry",
    "psychiatrist": "Psychiatry",
    "psychology": "Psychiatry",
    "mental health": "Psychiatry",
}


def normalize_department_name(raw_department: Optional[str]) -> Optional[str]:
    """
    Normalizes an informal department name to its canonical medical department.
    If no match is found, capitalizes words (Title Case).
    
    Examples:
        "dentist" -> "Dentistry"
        "heart" -> "Cardiology"
        "cardiology" -> "Cardiology"
        "neurologist" -> "Neurology"
    """
    if not raw_department:
        return None
        
    cleaned = raw_department.strip().lower()
    
    # 1. Exact lookup
    if cleaned in CANONICAL_DEPARTMENTS:
        return CANONICAL_DEPARTMENTS[cleaned]
        
    # 2. Substring matching
    for key, canonical in CANONICAL_DEPARTMENTS.items():
        if key in cleaned:
            return canonical
            
    # 3. Fallback: clean title case
    return raw_department.strip().title()
