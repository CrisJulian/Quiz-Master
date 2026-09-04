import pathlib
import config

CACHE_DIR = pathlib.Path(__file__).resolve().parent


def cache_path_for(email_or_uid):
    safe = "".join(c if c.isalnum() else "_" for c in (email_or_uid or "guest").lower())
    return CACHE_DIR / f"quiz_master_cache_{safe}.json"


_cache_path_for = cache_path_for


def slugify(text):
    """Turn a title into a stable, Firebase-safe key ('World History Quiz' -> 'world_history_quiz')."""
    cleaned = "".join(c if c.isalnum() else "_" for c in str(text).strip().lower())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "item"


SAMPLE_QUIZZES = [
    {
        "id": "BIO101",
        "code": "BIO101",
        "title": "(Example) Cellular Biology Midterm",
        "subject": "Biology",
        "category": "Science",
        "description": "Covers cellular respiration, photosynthesis, organelle structures, and membrane transport fundamentals.",
        "difficulty": "Intermediate",
        "time_mins": 15,
        "edited": "Edited 2h ago",
        "badge_color": config.PRIMARY,
        "badge_bg": config.PRIMARY_LIGHT,
        "icon": "🔬",
        "students_taken": 142,
        "questions": [
            {
                "question": "What is the primary function of mitochondria in a eukaryotic cell?",
                "options": [
                    "Protein synthesis and modification",
                    "Cellular respiration and ATP energy production",
                    "Photosynthesis and glucose storage",
                    "Lipid synthesis and packaging",
                ],
                "correct_index": 1,
                "explanation": "Mitochondria are known as the powerhouse of the cell, generating most ATP energy.",
            },
            {
                "question": "Which organelle is primarily responsible for protein synthesis?",
                "options": ["Ribosome", "Lysosome", "Golgi Apparatus", "Vacuole"],
                "correct_index": 0,
                "explanation": "Ribosomes translate mRNA sequences into polypeptide chains.",
            },
            {
                "question": "What is the process by which plants convert sunlight into biochemical energy?",
                "options": ["Fermentation", "Glycolysis", "Photosynthesis", "Oxidative Phosphorylation"],
                "correct_index": 2,
                "explanation": "Photosynthesis captures light energy to produce glucose.",
            },
            {
                "question": "Which process moves water molecules across a semi-permeable membrane?",
                "options": ["Active Transport", "Endocytosis", "Osmosis", "Phagocytosis"],
                "correct_index": 2,
                "explanation": "Osmosis is the passive diffusion of water across a semi-permeable membrane.",
            },
            {
                "question": "Which macromolecule constitutes the primary bilayer of cell membranes?",
                "options": ["Phospholipids", "Polysaccharides", "Triglycerides", "Nucleic Acids"],
                "correct_index": 0,
                "explanation": "Phospholipids form the foundational phospholipid bilayer of biological membranes.",
            },
        ],
    },
]

SAMPLE_DRAFTS = []
