"""Seed script for WanderLust AI destinations catalog in Firestore."""

from google.cloud import firestore

FIRESTORE_PROJECT = "qwiklabs-gcp-04-e27338d0990d"

DESTINATIONS = [
    {
        "id": "kyoto-japan",
        "name": "Kyoto, Japan",
        "country": "Japan",
        "travel_style": "Cultural & Scenic",
        "budget_tier": "Moderate",
        "avg_daily_cost_usd": 160,
        "best_season": "Spring (Cherry Blossoms) or Autumn",
        "highlights": [
            "Fushimi Inari Shrine",
            "Arashiyama Bamboo Grove",
            "Kinkaku-ji (Golden Pavilion)",
            "Gion Geisha District",
        ],
        "tags": ["temples", "nature", "culinary", "walkable", "historic"],
        "description": "The historic heart of traditional Japan, filled with ancient wooden temples, serene gardens, and sublime seasonal foliage.",
        "postcard_url": "https://storage.googleapis.com/wanderlust-ai-e27338d0990d-assets/postcards/kyoto_japan_20260930_211854.png",
    },
    {
        "id": "amalfi-italy",
        "name": "Amalfi Coast, Italy",
        "country": "Italy",
        "travel_style": "Romance & Coastal Luxury",
        "budget_tier": "Luxury",
        "avg_daily_cost_usd": 380,
        "best_season": "May to September",
        "highlights": [
            "Positano cliffside villas",
            "Ravello gardens",
            "Path of the Gods hike",
            "Boat charter to Capri",
        ],
        "tags": ["beach", "scenic", "luxury", "culinary", "romantic"],
        "description": "Dramatic Mediterranean cliffs lined with pastel fishing villages, lemon orchards, and world-class seaside dining.",
    },
    {
        "id": "banff-canada",
        "name": "Banff National Park, Canada",
        "country": "Canada",
        "travel_style": "Outdoor & Adventure",
        "budget_tier": "Moderate",
        "avg_daily_cost_usd": 210,
        "best_season": "June to August (hiking) or Dec to March (skiing)",
        "highlights": [
            "Lake Louise canoe rental",
            "Moraine Lake sunrise",
            "Icefields Parkway drive",
            "Johnston Canyon trail",
        ],
        "tags": ["mountains", "hiking", "wildlife", "adventure", "nature"],
        "description": "Majestic turquoise glacial lakes surrounded by soaring Canadian Rocky Mountain peaks and alpine wildlife.",
        "postcard_url": "https://storage.googleapis.com/wanderlust-ai-e27338d0990d-assets/postcards/banff_national_park_20260930_214538.jpg",
    },
    {
        "id": "oaxaca-mexico",
        "name": "Oaxaca City, Mexico",
        "country": "Mexico",
        "travel_style": "Culinary & Artisan Culture",
        "budget_tier": "Budget",
        "avg_daily_cost_usd": 95,
        "best_season": "October to March",
        "highlights": [
            "Monte Albán Zapotec ruins",
            "Mercado 20 de Noviembre food hall",
            "Hierve el Agua petrified waterfalls",
            "Mezcal distillery tour",
        ],
        "tags": ["culinary", "foodie", "culture", "indigenous", "budget-friendly"],
        "description": "Mexico's culinary capital, renowned for complex moles, artisanal mezcal, vibrant textile crafts, and colonial architecture.",
    },
    {
        "id": "queenstown-nz",
        "name": "Queenstown, New Zealand",
        "country": "New Zealand",
        "travel_style": "Action & Nature Thrills",
        "budget_tier": "Moderate to Luxury",
        "avg_daily_cost_usd": 240,
        "best_season": "December to February (summer) or July to August (snow)",
        "highlights": [
            "Milford Sound fjord cruise",
            "Shotover River jet boating",
            "Bungy jump at Kawarau Bridge",
            "Central Otago Pinot Noir tasting",
        ],
        "tags": ["adventure", "mountains", "lakes", "wine", "extreme-sports"],
        "description": "The world's adventure capital nestled on the shores of Lake Wakatipu beneath the dramatic Remarkables mountain range.",
    },
]


def seed_database():
    db = firestore.Client(project=FIRESTORE_PROJECT)
    collection_ref = db.collection("destinations")

    print(f"Connecting to Firestore for project: {FIRESTORE_PROJECT}")
    for dest in DESTINATIONS:
        doc_id = dest["id"]
        collection_ref.document(doc_id).set(dest)
        print(f"Seeded destination: {dest['name']} (ID: {doc_id})")

    print(f"Successfully seeded {len(DESTINATIONS)} destinations into 'destinations' collection.")


if __name__ == "__main__":
    seed_database()
