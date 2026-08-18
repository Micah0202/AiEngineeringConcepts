lookup_weather_schema = {
    "type": "function",
    "function": {
        "name": "lookup_weather",
        "description": (
            "Look up CURRENT, live weather for a place using Open-Meteo API."
            "Use this whenever the user asks for the weather in a location, or for wind speed, sky conditions or temperature."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The name of the location to look up the weather for. Eg 'London', 'Paris', 'New York'."
                }
            },
            "required": ["location"],
        }
    }
}

TOOL_MENU = [lookup_weather_schema]

def tool_catalog() -> list[dict[str, str]]:
    return [
        {
            "name": schema["function"]["name"],
            "description": schema["function"]["description"],
        } for schema in TOOL_MENU
    ]