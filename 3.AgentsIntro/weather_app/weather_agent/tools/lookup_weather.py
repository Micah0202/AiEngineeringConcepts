import requests

from weather_agent.config import GEOCODE_URL, WEATHER_REQUEST_TIMEOUT, FORECAST_URL

#dictionary  for the weather codes 
WEATHER_CODES: dict[int, str] = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    80: "rain showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
}

#this location paramter will  be fetched from the llm and then the python code will make the tool call 
#this is our tool 
def lookup_weather(location: str) -> str:
    try:
        #gives us the latitude and longitude for a string . 
        geo = requests.get(
            GEOCODE_URL,
            #location passed as request param
            params={"name": location, "count": 1},
            timeout=WEATHER_REQUEST_TIMEOUT,
        )

        geo.raise_for_status()
        matches = geo.json().get("results")
        print( matches[0])
        if not matches:
            return f"We couldn't find a place called {location}"
        
        place = matches[0]
        lat, lon = place["latitude"], place["longitude"]

        label = ", ".join(
            part for part in (place.get("name"), place.get("country")) if part
        ) # join the name and country with a comma

        forecast = requests.get(
            FORECAST_URL,
            params={"latitude": lat, "longitude": lon, "current": "temperature_2m,weather_code,wind_speed_10m"}, # get the current temperature, weather code, and wind speed
            timeout=WEATHER_REQUEST_TIMEOUT,
        )

        forecast.raise_for_status()
        current = forecast.json().get("current")

        temperature = current.get("temperature_2m")
        weather_code = current.get("weather_code")
        wind_speed = current.get("wind_speed_10m")

        sky = WEATHER_CODES.get(weather_code, f"weather code {weather_code}")
        wind_note = f", wind {wind_speed} km/h" if wind_speed else ""

        return f"The current temperature in {label} is {temperature}°C, the sky is {sky}{wind_note}."
        
    except requests.exceptions.RequestException as err:
        return f"We couldn't look up the weather for {location}: {err}"
    except Exception as err:
        return f"Unexpected weather response error: {err}"

