# The model reads lookup_weather_schema and emits {"location": "Tokyo"}. Your loop looks that name up in TOOL_FUNCTIONS, gets the function, and calls it. The schema is the menu; the function is the kitchen; the registry is the waiter.



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

#prepare an array of dictionaries that has the name and description 
def tool_catalog() -> list[dict[str, str]]:
    return [
        {
            "name": schema["function"]["name"],
            "description": schema["function"]["description"],
        } for schema in TOOL_MENU
    ]