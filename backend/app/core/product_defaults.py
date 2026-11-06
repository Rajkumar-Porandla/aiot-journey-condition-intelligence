"""Product categories and *demonstration* environmental profiles.

IMPORTANT: These values are prototype defaults chosen for a software-only
course project. They are loosely inspired by common cold-chain practice but
are NOT universal safety or storage standards. Real products must follow the
manufacturer's / regulator's specifications.
"""

CATEGORIES = {
    "fruits_vegetables": "Fruits and Vegetables",
    "dairy": "Dairy Products",
    "frozen": "Frozen Products",
    "pharmaceutical": "Pharmaceutical Products",
    "flowers": "Flowers",
}
CATEGORY_KEYS = list(CATEGORIES.keys())

SENSITIVITY_LEVELS = ("Low", "Medium", "High", "Very High")

# Demonstration default profiles (one per category, seeded into the database)
DEFAULT_PROFILES = {
    "fruits_vegetables": {
        "name": "Fresh Produce (Demo Default)",
        "min_temp": 4.0,
        "max_temp": 12.0,
        "min_humidity": 80.0,
        "max_humidity": 95.0,
        "sensitivity": "Medium",
        "description": "Demonstration profile for mixed fresh fruits and vegetables. "
        "Warm exposure accelerates ripening; very cold air may cause chilling injury.",
    },
    "dairy": {
        "name": "Chilled Dairy (Demo Default)",
        "min_temp": 2.0,
        "max_temp": 6.0,
        "min_humidity": 60.0,
        "max_humidity": 85.0,
        "sensitivity": "High",
        "description": "Demonstration profile for milk, yoghurt and cheese. "
        "Temperature is the dominant factor; humidity has a smaller effect.",
    },
    "frozen": {
        "name": "Frozen Goods (Demo Default)",
        "min_temp": -25.0,
        "max_temp": -15.0,
        "min_humidity": 50.0,
        "max_humidity": 90.0,
        "sensitivity": "High",
        "description": "Demonstration profile for frozen foods. Warm excursions "
        "(partial thawing) are the main concern.",
    },
    "pharmaceutical": {
        "name": "Cold-Chain Pharma 2-8°C (Demo Default)",
        "min_temp": 2.0,
        "max_temp": 8.0,
        "min_humidity": 35.0,
        "max_humidity": 60.0,
        "sensitivity": "Very High",
        "description": "Demonstration profile for temperature-sensitive medicines. "
        "Both warm excursions and freezing are treated as harmful.",
    },
    "flowers": {
        "name": "Cut Flowers (Demo Default)",
        "min_temp": 1.0,
        "max_temp": 8.0,
        "min_humidity": 80.0,
        "max_humidity": 95.0,
        "sensitivity": "Medium",
        "description": "Demonstration profile for cut flowers. Warmth and dry air "
        "shorten vase life.",
    },
}


def category_label(key):
    return CATEGORIES.get(key, key) if key else None


def default_profile(category: str) -> dict:
    profile = dict(DEFAULT_PROFILES[category])
    profile["category"] = category
    return profile

