# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import pathlib
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors.agent_engine_sandbox_code_executor import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore
from google.genai import types

from .a2ui_utils import a2ui_callback

try:
    from a2ui.schema.manager import A2uiSchemaManager
    from a2ui.basic_catalog.provider import BasicCatalog
    HAS_A2UI_SDK = True
except ImportError:
    HAS_A2UI_SDK = False

MODEL = "gemini-3.6-flash"

# Hardcoded project ID to avoid Agent Platform resolving to project number
FIRESTORE_PROJECT = "qwiklabs-gcp-04-e27338d0990d"


def _get_db():
    return firestore.Client(project=FIRESTORE_PROJECT)


def search_destinations(
    query: Optional[str] = None,
    budget_tier: Optional[str] = None,
    tag: Optional[str] = None,
    max_daily_budget_usd: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Search or list travel destinations from the catalog in Firestore.

    Args:
        query: Optional text to filter destination name, country, or description.
        budget_tier: Optional budget tier to filter by ("Budget", "Moderate", "Luxury").
        tag: Optional tag to filter by (e.g. "beach", "culinary", "mountains", "culture", "adventure").
        max_daily_budget_usd: Optional upper limit for average daily cost in USD.

    Returns:
        A list of matching destination items.
    """
    db = _get_db()
    docs = db.collection("destinations").stream()
    results = []

    for doc in docs:
        item = doc.to_dict()
        if budget_tier and item.get("budget_tier", "").lower() != budget_tier.lower():
            continue
        if max_daily_budget_usd and item.get("avg_daily_cost_usd", 0) > max_daily_budget_usd:
            continue
        if tag:
            tags = [t.lower() for t in item.get("tags", [])]
            if tag.lower() not in tags:
                continue
        if query:
            q = query.lower()
            name_match = q in item.get("name", "").lower()
            country_match = q in item.get("country", "").lower()
            desc_match = q in item.get("description", "").lower()
            if not (name_match or country_match or desc_match):
                continue
        results.append(item)

    return results


def get_destination_details(destination_id: str) -> Dict[str, Any]:
    """Retrieve full details for a specific travel destination by ID.

    Args:
        destination_id: The unique ID of the destination (e.g. "kyoto-japan", "amalfi-italy").

    Returns:
        The destination record dictionary or an error message.
    """
    db = _get_db()
    doc = db.collection("destinations").document(destination_id).get()
    if not doc.exists:
        return {"error": f"Destination with ID '{destination_id}' not found."}
    return doc.to_dict()


def save_travel_itinerary(
    destination_name: str,
    traveler_name: str,
    duration_days: int,
    itinerary_notes: str,
    estimated_total_cost_usd: Optional[int] = None,
) -> Dict[str, Any]:
    """Save a traveler's planned itinerary to the Firestore 'itineraries' collection.

    Args:
        destination_name: Name of the destination (e.g. "Kyoto, Japan").
        traveler_name: Name of the traveler.
        duration_days: Number of days for the trip.
        itinerary_notes: Summary or day-by-day plan for the itinerary.
        estimated_total_cost_usd: Optional estimated total trip budget/cost in USD.

    Returns:
        A confirmation dictionary including the generated itinerary record ID.
    """
    db = _get_db()
    doc_ref = db.collection("itineraries").document()
    record = {
        "id": doc_ref.id,
        "destination_name": destination_name,
        "traveler_name": traveler_name,
        "duration_days": duration_days,
        "itinerary_notes": itinerary_notes,
        "estimated_total_cost_usd": estimated_total_cost_usd,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    doc_ref.set(record)
    return {"status": "success", "itinerary_id": doc_ref.id, "record": record}


def get_weather(query: str) -> str:
    """Fetch real-time weather and forecast conditions for any travel destination using Open-Meteo API.

    Args:
        query: Destination or city name (e.g. "Kyoto", "Amalfi", "Banff", "Oaxaca").

    Returns:
        A formatted string with live temperature, conditions, and wind speed.
    """
    import urllib.parse
    import urllib.request
    import json

    # Clean location query
    loc_clean = query.split(",")[0].strip()

    try:
        # Step 1: Geocode city name to lat/lon
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(loc_clean)}&count=1&language=en&format=json"
        req = urllib.request.Request(geo_url, headers={"User-Agent": "WanderLust-AI/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            geo_data = json.loads(response.read().decode())

        if not geo_data.get("results"):
            return f"Could not find live weather coordinates for '{query}'."

        first_match = geo_data["results"][0]
        lat = first_match["latitude"]
        lon = first_match["longitude"]
        place_name = f"{first_match.get('name')}, {first_match.get('country', '')}".strip(", ")

        # Step 2: Fetch current weather
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        req_w = urllib.request.Request(weather_url, headers={"User-Agent": "WanderLust-AI/1.0"})
        with urllib.request.urlopen(req_w, timeout=5) as response_w:
            w_data = json.loads(response_w.read().decode())

        curr = w_data.get("current_weather", {})
        temp_c = curr.get("temperature", "N/A")
        temp_f = round(temp_c * 9 / 5 + 32, 1) if isinstance(temp_c, (int, float)) else "N/A"
        wind = curr.get("windspeed", "N/A")
        code = curr.get("weathercode", 0)

        # Basic WMO weather code translation
        conditions = "Clear skies"
        if code in [1, 2, 3]:
            conditions = "Mainly clear to partly cloudy"
        elif code in [45, 48]:
            conditions = "Foggy"
        elif code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
            conditions = "Rain showers"
        elif code in [71, 73, 75, 85, 86]:
            conditions = "Snow flurries"
        elif code >= 95:
            conditions = "Thunderstorms"

        return f"Live weather in {place_name}: {temp_f}°F ({temp_c}°C), {conditions}, wind at {wind} km/h."
    except Exception as e:
        return f"Unable to fetch live weather for '{query}': {str(e)}"


def calculate_trip_budget(
    destination_name: str,
    duration_days: int,
    num_travelers: int = 1,
    budget_tier: str = "Moderate",
    target_currency: str = "USD",
) -> Dict[str, Any]:
    """Calculate an itemized travel budget estimate and convert into target currency.

    Args:
        destination_name: Name of destination (e.g. "Kyoto, Japan", "Amalfi Coast, Italy").
        duration_days: Number of days for the trip.
        num_travelers: Number of people traveling (default 1).
        budget_tier: Travel style tier - "Budget", "Moderate", or "Luxury".
        target_currency: Target currency code - "USD", "EUR", "JPY", "GBP", "CAD", "MXN", "NZD".

    Returns:
        An itemized breakdown of lodging, meals, activities, local transit, total USD, and target currency conversion.
    """
    # Daily benchmark rates in USD per person by tier
    benchmarks = {
        "budget": {"lodging": 45, "food": 30, "activities": 15, "transit": 10},
        "moderate": {"lodging": 90, "food": 50, "activities": 35, "transit": 15},
        "luxury": {"lodging": 220, "food": 110, "activities": 80, "transit": 40},
    }

    # Exchange rates relative to 1 USD
    fx_rates = {
        "USD": 1.0,
        "EUR": 0.92,
        "JPY": 152.5,
        "GBP": 0.78,
        "CAD": 1.38,
        "MXN": 19.4,
        "NZD": 1.65,
    }

    tier_key = budget_tier.lower()
    rates = benchmarks.get(tier_key, benchmarks["moderate"])

    daily_lodging = rates["lodging"] * max(1, (num_travelers + 1) // 2)  # assumed double occupancy
    daily_food = rates["food"] * num_travelers
    daily_activities = rates["activities"] * num_travelers
    daily_transit = rates["transit"] * num_travelers
    daily_total_usd = daily_lodging + daily_food + daily_activities + daily_transit

    total_lodging_usd = daily_lodging * duration_days
    total_food_usd = daily_food * duration_days
    total_activities_usd = daily_activities * duration_days
    total_transit_usd = daily_transit * duration_days
    total_cost_usd = daily_total_usd * duration_days

    currency_code = target_currency.upper()
    fx = fx_rates.get(currency_code, 1.0)
    total_in_target_currency = round(total_cost_usd * fx, 2)

    return {
        "destination": destination_name,
        "duration_days": duration_days,
        "num_travelers": num_travelers,
        "budget_tier": budget_tier.capitalize(),
        "breakdown_usd": {
            "lodging_total": total_lodging_usd,
            "meals_dining_total": total_food_usd,
            "activities_sightseeing_total": total_activities_usd,
            "local_transit_total": total_transit_usd,
            "daily_total_usd": daily_total_usd,
            "grand_total_usd": total_cost_usd,
        },
        "currency_conversion": {
            "target_currency": currency_code,
            "exchange_rate": fx,
            "grand_total_target_currency": total_in_target_currency,
        },
    }


def generate_travel_postcard(
    tool_context: ToolContext,
    destination_name: str,
    visual_style: str = "watercolor artistic style",
) -> Dict[str, Any]:
    """Generate an AI travel postcard image for a destination using gemini-3.1-flash-lite-image,
    save it to session artifacts, and upload to public Cloud Storage.

    Args:
        tool_context: ADK ToolContext for managing session artifacts.
        destination_name: Name of the destination (e.g. "Kyoto, Japan", "Amalfi Coast, Italy").
        visual_style: Aesthetic style (e.g. "watercolor artistic style", "vintage travel poster", "vibrant photography").

    Returns:
        A dictionary with the destination, image public URL, and caption.
    """
    from google import genai
    from google.cloud import storage

    client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT, location="global")
    prompt = f"Scenic travel postcard of {destination_name}, {visual_style}, high quality"

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=prompt,
    )

    image_bytes = None
    mime_type = "image/jpeg"
    for part in response.candidates[0].content.parts:
        if part.inline_data:
            image_bytes = part.inline_data.data
            mime_type = part.inline_data.mime_type or "image/jpeg"
            break

    if not image_bytes:
        return {"error": f"Failed to generate postcard image for {destination_name}."}

    ext = "png" if "png" in mime_type else "jpg"
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_name = destination_name.lower().replace(" ", "_").replace(",", "")
    artifact_filename = f"{clean_name}_{timestamp}.{ext}"

    # 1. Save to session artifacts for Playground Artifacts panel
    artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    tool_context.save_artifact(filename=artifact_filename, artifact=artifact_part)

    # 2. Upload same bytes to public Cloud Storage bucket
    bucket_name = "wanderlust-ai-e27338d0990d-assets"
    storage_client = storage.Client(project=FIRESTORE_PROJECT)
    bucket = storage_client.bucket(bucket_name)

    storage_filename = f"postcards/{artifact_filename}"
    blob = bucket.blob(storage_filename)
    blob.upload_from_string(image_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{bucket_name}/{storage_filename}"

    return {
        "status": "success",
        "destination": destination_name,
        "style": visual_style,
        "artifact_filename": artifact_filename,
        "image_url": public_url,
        "caption": f"Postcard of {destination_name} in {visual_style}",
    }

def plan_daily_itinerary(
    destination_id: str,
    duration_days: int = 3,
    pace: str = "balanced",
) -> Dict[str, Any]:
    """Create a minimal day-by-day activity schedule and route from catalog highlights.

    Args:
        destination_id: Destination ID from catalog (e.g. "kyoto-japan", "amalfi-italy", "banff-canada").
        duration_days: Number of days to plan (default 3, 1-7 days).
        pace: Travel pace - "relaxed" (1 main activity/day) or "balanced" (2 activities/day).

    Returns:
        Structured day-by-day plan with morning/afternoon slots and transit tips.
    """
    dest = get_destination_details(destination_id)
    if "error" in dest:
        return dest

    highlights = dest.get("highlights", [])
    days_plan = []
    items_per_day = 1 if pace.lower() == "relaxed" else 2

    for day_num in range(1, duration_days + 1):
        idx = (day_num - 1) * items_per_day
        morning_act = highlights[idx % len(highlights)] if highlights else "Explore central historic area"
        
        if items_per_day == 2:
            afternoon_act = highlights[(idx + 1) % len(highlights)] if highlights else "Local cafe & neighborhood walk"
        else:
            afternoon_act = "Leisurely afternoon at local cafe or scenic viewpoint"

        days_plan.append({
            "day": day_num,
            "morning": morning_act,
            "afternoon": afternoon_act,
            "evening": f"Traditional dining in {dest.get('name', 'town')}",
            "route_tip": f"Group morning and afternoon stops to minimize transit time.",
        })

    return {
        "destination": dest.get("name"),
        "country": dest.get("country"),
        "duration_days": duration_days,
        "pace": pace.capitalize(),
        "daily_schedule": days_plan,
        "best_season": dest.get("best_season"),
    }


# WRITE: after each turn, send the session to Memory Bank for extraction.
async def generate_memories_callback(callback_context: CallbackContext):
    await callback_context.add_session_to_memory()
    return None


_prompt_file = pathlib.Path(__file__).parent / "instruction_prompt.txt"
if _prompt_file.exists():
    instruction = _prompt_file.read_text(encoding="utf-8")
elif HAS_A2UI_SDK:
    schema_manager = A2uiSchemaManager(
        version="0.8",
        catalogs=[BasicCatalog.get_config("0.8")],
    )
    instruction = schema_manager.generate_system_prompt(
        role_description=(
            "You are WanderLust AI, an expert travel concierge assistant. "
            "You remember the traveler's stated preferences, dietary restrictions, favorite destinations, "
            "and facts from previous conversations and use them to personalize your recommendations. "
            "You help travelers explore destinations, find spots matching their travel style, "
            "budget, and preferences, plan daily activity routes, calculate budgets, and save customized itineraries. "
            "Always use your Firestore tools (`search_destinations`, `get_destination_details`, `save_travel_itinerary`) "
            "to search our curated catalog and store traveler plans. "
            "Use `plan_daily_itinerary` when the user asks for a day-by-day schedule, route, or trip itinerary plan. "
            "Use `calculate_trip_budget` whenever the user asks about costs, budgets, price estimates, or currency conversions. "
            "Use `generate_travel_postcard` whenever the user asks for a visual, postcard, photo, picture, or moodboard of a destination. "
            "When an image is generated, display the markdown image link or include its public URL in an A2UI Image component. "
            "Use `get_weather` when travelers ask about destination conditions. "
            "You have access to a secure Python code execution sandbox. Whenever you need to execute code, "
            "write Python code enclosed in ```python\n...\n``` or ```tool_code\n...\n``` blocks and print the outputs. "
            "The sandbox executes your code and preserves variable state across steps."
        ),
        workflow_description=(
            "Analyze the traveler's request and return structured UI when appropriate. "
            "When displaying destinations from search_destinations or get_destination_details (especially Kyoto or Banff), "
            "render an A2UI Card for each destination with its title, highlights/details, and if a postcard_url or image_url "
            "is present in the destination record, include an Image component displaying that postcard URL."
        ),
        ui_description=(
            "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows and an optional Image. "
            "Never nest a Card inside a Card. "
            "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
            "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
            "nothing in adk web). "
            "When presenting destinations such as Kyoto or Banff that have a postcard_url or image_url, "
            "include an Image component pointing to that exact public https URL, for example "
            "{\"Image\": {\"url\": {\"literalString\": \"https://storage.googleapis.com/...\"}}}. "
            "You may also include an Image component when generate_travel_postcard returns a public https URL. "
            "Never point an Image at a bare filename, an artifact name, or a non-http(s) path. If you "
            "do not have a public URL, add a short Text line noting the details instead. "
            "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
            "headings and emphasis. "
            "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
            "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
        ),
        include_schema=True,
        include_examples=True,
    )
else:
    instruction = "You are WanderLust AI, an expert travel concierge assistant."


root_agent = Agent(
    name="wanderlust_agent",
    model=Gemini(
        model=MODEL,
        client_kwargs={"location": "global"},
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    code_executor=AgentEngineSandboxCodeExecutor(
        sandbox_resource_name="projects/787379903740/locations/us-east1/reasoningEngines/1012357739088707584/sandboxEnvironments/4644838493028089856",
        agent_engine_resource_name="projects/787379903740/locations/us-east1/reasoningEngines/1012357739088707584",
    ),
    tools=[
        PreloadMemoryTool(),
        search_destinations,
        get_destination_details,
        plan_daily_itinerary,
        calculate_trip_budget,
        generate_travel_postcard,
        save_travel_itinerary,
        get_weather,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
