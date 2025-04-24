from typing import Optional, Dict, Any, List, Tuple
import sys
import os
from datetime import datetime, timedelta
import httpx
import json
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("ultrahuman")

# Get configuration from environment variables
ULTRAHUMAN_API_BASE = "https://partner.ultrahuman.com/api/v1"
AUTH_TOKEN = os.getenv("ULTRAHUMAN_API_TOKEN")
DEFAULT_EMAIL = os.getenv("DEFAULT_EMAIL")

# Check if required env variables are set
# Check if required env variables are set
if not AUTH_TOKEN:
    print("ERROR: ULTRAHUMAN_API_TOKEN not set in .env file", file=sys.stderr)
    sys.exit(1)  # Exit with error instead of using fallback

async def fetch_ultrahuman_data(email: str, date: str) -> Dict[str, Any]:
    """Fetch data from Ultrahuman API for a specific date."""
    url = f"{ULTRAHUMAN_API_BASE}/metrics"

    headers = {
        "Authorization": AUTH_TOKEN
    }

    params = {
        "email": email,
        "date": date
    }

    print(f"Making API request to {url} with params: {params}", file=sys.stderr)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params, timeout=30.0)
            print(f"Response status: {response.status_code}", file=sys.stderr)

            # Make sure we have a valid response
            response.raise_for_status()

            # Now try to parse JSON
            try:
                return response.json()
            except json.JSONDecodeError as e:
                print(f"JSON parse error: {e}", file=sys.stderr)
                return {"api_error": f"Invalid JSON response: {e}"}

    except httpx.HTTPStatusError as e:
        print(f"HTTP error: {e.response.status_code} - {e.response.text}", file=sys.stderr)
        return {"api_error": f"HTTP error: {e.response.status_code}"}
    except httpx.RequestError as e:
        print(f"Request error: {e}", file=sys.stderr)
        return {"api_error": f"Request error: {e}"}
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return {"api_error": f"Unexpected error: {str(e)}"}

def extract_metrics_data(api_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Extract heart rate, sleep, HRV, and temperature data from API response."""
    try:
        metric_data = api_data.get("data", {}).get("metric_data", [])

        # Extract heart rate data
        hr_data = next((m for m in metric_data if m["type"] == "hr"), None)
        hr_values = hr_data.get("object", {}).get("values", []) if hr_data else []

        # Extract sleep data
        sleep_data = next((m for m in metric_data if m["type"] == "Sleep"), None)
        sleep_obj = sleep_data.get("object", {}) if sleep_data else {}

        # Extract HRV data
        hrv_data = next((m for m in metric_data if m["type"] == "hrv"), None)
        hrv_values = hrv_data.get("object", {}).get("values", []) if hrv_data else []

        # Extract temperature data
        temp_data = next((m for m in metric_data if m["type"] == "temp"), None)
        temp_values = temp_data.get("object", {}).get("values", []) if temp_data else []

        return hr_values, sleep_obj, hrv_values, temp_values
    except Exception as e:
        print(f"Error extracting metrics: {e}", file=sys.stderr)
        return [], {}, [], []

def find_heart_rate_drops(hr_values: List[Dict[str, Any]], sleep_obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find significant heart rate drops during sleep."""
    try:
        # Get sleep time range
        bedtime_start = sleep_obj.get("bedtime_start")
        bedtime_end = sleep_obj.get("bedtime_end")

        if not bedtime_start or not bedtime_end:
            return []

        # Filter heart rate readings during sleep
        sleep_hr_values = [hr for hr in hr_values if hr["timestamp"] >= bedtime_start and hr["timestamp"] <= bedtime_end]

        # Sort by timestamp
        sorted_data = sorted(sleep_hr_values, key=lambda x: x["timestamp"])

        drops = []
        prev_hr = None
        prev_timestamp = None

        # Look for significant drops
        for entry in sorted_data:
            current_hr = entry["value"]
            timestamp = entry["timestamp"]

            if prev_hr is not None:
                # Define a significant drop (e.g., more than 10 BPM)
                hr_change = current_hr - prev_hr

                if hr_change <= -10:  # A drop of 10 BPM or more
                    # Calculate time difference in minutes
                    time_diff_seconds = (timestamp - prev_timestamp)
                    time_diff_minutes = time_diff_seconds / 60

                    # Only consider drops that happen within a reasonable timeframe
                    if time_diff_minutes <= 30:
                        drops.append({
                            "timestamp": timestamp,
                            "datetime": datetime.fromtimestamp(timestamp),
                            "from_hr": prev_hr,
                            "to_hr": current_hr,
                            "drop": abs(hr_change),
                            "time_diff_minutes": time_diff_minutes
                        })

            prev_hr = current_hr
            prev_timestamp = timestamp

        return drops
    except Exception as e:
        print(f"Error finding heart rate drops: {e}", file=sys.stderr)
        return []

def find_lowest_heart_rate(hr_values: List[Dict[str, Any]], sleep_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Find the lowest heart rate reading during sleep."""
    try:
        # Get sleep time range
        bedtime_start = sleep_obj.get("bedtime_start")
        bedtime_end = sleep_obj.get("bedtime_end")

        if not bedtime_start or not bedtime_end:
            return {}

        # Filter heart rate readings during sleep
        sleep_hr_values = [hr for hr in hr_values if hr["timestamp"] >= bedtime_start and hr["timestamp"] <= bedtime_end]

        if not sleep_hr_values:
            return {}

        # Find the entry with the lowest heart rate value
        lowest_hr = min(sleep_hr_values, key=lambda x: x["value"])

        return {
            "value": lowest_hr["value"],
            "timestamp": lowest_hr["timestamp"],
            "datetime": datetime.fromtimestamp(lowest_hr["timestamp"])
        }
    except Exception as e:
        print(f"Error finding lowest heart rate: {e}", file=sys.stderr)
        return {}

def get_sleep_metrics(sleep_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and calculate sleep metrics."""
    try:
        if not sleep_obj:
            return {}

        bedtime_start = sleep_obj.get("bedtime_start")
        bedtime_end = sleep_obj.get("bedtime_end")

        if not bedtime_start or not bedtime_end:
            return {}

        # Calculate basic sleep metrics
        sleep_duration_seconds = bedtime_end - bedtime_start
        sleep_duration_minutes = sleep_duration_seconds / 60
        sleep_hours = int(sleep_duration_minutes // 60)
        sleep_minutes = int(sleep_duration_minutes % 60)

        # Get sleep stages if available
        sleep_stages = sleep_obj.get("sleep_stages", [])
        deep_sleep = next((stage for stage in sleep_stages if stage.get("type") == "deep_sleep"), {})
        light_sleep = next((stage for stage in sleep_stages if stage.get("type") == "light_sleep"), {})
        rem_sleep = next((stage for stage in sleep_stages if stage.get("type") == "rem_sleep"), {})
        awake = next((stage for stage in sleep_stages if stage.get("type") == "awake"), {})

        return {
            "start": datetime.fromtimestamp(bedtime_start),
            "end": datetime.fromtimestamp(bedtime_end),
            "duration_minutes": sleep_duration_minutes,
            "duration_formatted": f"{sleep_hours}h {sleep_minutes}m",
            "deep_sleep_percentage": deep_sleep.get("percentage", 0),
            "light_sleep_percentage": light_sleep.get("percentage", 0),
            "rem_percentage": rem_sleep.get("percentage", 0),
            "awake_percentage": awake.get("percentage", 0)
        }
    except Exception as e:
        print(f"Error getting sleep metrics: {e}", file=sys.stderr)
        return {}

def analyze_temperature_data(temp_values: List[Dict[str, Any]], sleep_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze skin temperature data during sleep period."""
    try:
        # Get sleep time range
        bedtime_start = sleep_obj.get("bedtime_start")
        bedtime_end = sleep_obj.get("bedtime_end")

        if not bedtime_start or not bedtime_end or not temp_values:
            return {}

        # Filter temperature readings during sleep
        sleep_temp_values = [temp for temp in temp_values if
                            temp["timestamp"] >= bedtime_start and
                            temp["timestamp"] <= bedtime_end]

        if not sleep_temp_values:
            return {}

        # Sort by timestamp
        sorted_data = sorted(sleep_temp_values, key=lambda x: x["timestamp"])

        # Calculate min, max, average
        temp_values_only = [temp["value"] for temp in sorted_data]
        min_temp = min(temp_values_only)
        max_temp = max(temp_values_only)
        avg_temp = sum(temp_values_only) / len(temp_values_only)

        # Calculate temperature variation (max - min)
        temp_variation = max_temp - min_temp

        # Find when the lowest and highest temperatures occurred
        min_temp_entry = min(sorted_data, key=lambda x: x["value"])
        max_temp_entry = max(sorted_data, key=lambda x: x["value"])

        # Calculate temperature at sleep onset and before waking
        early_sleep_temps = [temp for temp in sorted_data if temp["timestamp"] - bedtime_start <= 1800]  # First 30 min
        late_sleep_temps = [temp for temp in sorted_data if bedtime_end - temp["timestamp"] <= 1800]    # Last 30 min

        early_sleep_avg = sum([temp["value"] for temp in early_sleep_temps]) / len(early_sleep_temps) if early_sleep_temps else None
        late_sleep_avg = sum([temp["value"] for temp in late_sleep_temps]) / len(late_sleep_temps) if late_sleep_temps else None

        # Detect significant temperature drops during sleep (more than 1°C)
        temp_drops = []
        prev_temp = None
        prev_timestamp = None

        for entry in sorted_data:
            current_temp = entry["value"]
            timestamp = entry["timestamp"]

            if prev_temp is not None:
                temp_change = current_temp - prev_temp

                if temp_change <= -1.0:  # Drop of 1°C or more
                    time_diff_minutes = (timestamp - prev_timestamp) / 60

                    temp_drops.append({
                        "timestamp": timestamp,
                        "datetime": datetime.fromtimestamp(timestamp),
                        "from_temp": round(prev_temp, 2),
                        "to_temp": round(current_temp, 2),
                        "drop": round(abs(temp_change), 2),
                        "time_diff_minutes": time_diff_minutes
                    })

            prev_temp = current_temp
            prev_timestamp = timestamp

        return {
            "min_temp": round(min_temp, 2),
            "max_temp": round(max_temp, 2),
            "avg_temp": round(avg_temp, 2),
            "variation": round(temp_variation, 2),
            "min_temp_time": datetime.fromtimestamp(min_temp_entry["timestamp"]),
            "max_temp_time": datetime.fromtimestamp(max_temp_entry["timestamp"]),
            "early_sleep_avg": round(early_sleep_avg, 2) if early_sleep_avg is not None else None,
            "late_sleep_avg": round(late_sleep_avg, 2) if late_sleep_avg is not None else None,
            "temp_drops": temp_drops
        }
    except Exception as e:
        print(f"Error analyzing temperature data: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return {}

def format_analysis_results(
    sleep_metrics: Dict[str, Any],
    hr_drops: List[Dict[str, Any]],
    lowest_hr: Dict[str, Any],
    temp_analysis: Dict[str, Any],
    avg_hrv: Optional[int] = None
) -> str:
    """Format all analysis results into a readable report."""
    result = []

    # Add sleep details
    if sleep_metrics:
        result.append("Sleep Summary:")
        result.append(f"• Sleep Period: {sleep_metrics['start'].strftime('%I:%M %p')} to {sleep_metrics['end'].strftime('%I:%M %p')}")
        result.append(f"• Total Sleep Duration: {sleep_metrics['duration_formatted']}")

        # Add sleep stages if available
        if sleep_metrics.get("deep_sleep_percentage"):
            result.append("• Sleep Stages:")
            result.append(f"  - Deep Sleep: {sleep_metrics['deep_sleep_percentage']}%")
            result.append(f"  - Light Sleep: {sleep_metrics['light_sleep_percentage']}%")
            result.append(f"  - REM Sleep: {sleep_metrics['rem_percentage']}%")
            result.append(f"  - Awake: {sleep_metrics['awake_percentage']}%")

        result.append("")

    # Add heart rate analysis
    result.append("Heart Rate Analysis:")

    # Add lowest heart rate details
    if lowest_hr and "value" in lowest_hr:
        result.append(f"• Lowest Heart Rate: {lowest_hr['value']} BPM at {lowest_hr['datetime'].strftime('%I:%M %p')}")
    else:
        result.append("• Lowest Heart Rate: Data not available")

    # Add HRV if available
    if avg_hrv is not None:
        result.append(f"• Average HRV: {avg_hrv} ms")

    result.append("")

    # Add temperature analysis if available
    if temp_analysis:
        result.append("Temperature Analysis:")
        result.append(f"• Average Skin Temperature: {temp_analysis['avg_temp']}°C")
        result.append(f"• Range: {temp_analysis['min_temp']}°C - {temp_analysis['max_temp']}°C (variation: {temp_analysis['variation']}°C)")

        if temp_analysis.get('early_sleep_avg') and temp_analysis.get('late_sleep_avg'):
            early_temp = temp_analysis['early_sleep_avg']
            late_temp = temp_analysis['late_sleep_avg']
            temp_change = late_temp - early_temp
            change_direction = "increased" if temp_change > 0 else "decreased"

            result.append(f"• Temperature {change_direction} by {abs(round(temp_change, 2))}°C during sleep")
            result.append(f"  - Early sleep: {early_temp}°C")
            result.append(f"  - Late sleep: {late_temp}°C")

        # Add significant temperature drops if any
        if temp_analysis.get('temp_drops'):
            result.append(f"• Significant Temperature Drops: {len(temp_analysis['temp_drops'])}")

            for drop in temp_analysis['temp_drops'][:3]:  # Show at most 3 drops
                result.append(f"  - {drop['from_temp']}°C to {drop['to_temp']}°C at {drop['datetime'].strftime('%I:%M %p')}")

        result.append("")

    # Add heart rate drops details
    if hr_drops:
        result.append(f"Significant Heart Rate Drops ({len(hr_drops)}):")

        for i, drop in enumerate(hr_drops, 1):
            result.append(f"Drop #{i}:")
            result.append(f"• Time: {drop['datetime'].strftime('%I:%M %p')}")
            result.append(f"• Decreased from {drop['from_hr']} to {drop['to_hr']} BPM")
            result.append(f"• Total drop: {drop['drop']} BPM")
            if i < len(hr_drops):
                result.append("")  # Add space between drops
    else:
        result.append("No significant heart rate drops detected during sleep.")

    return "\n".join(result)

@mcp.tool()
async def analyze_night_heart_rate(email: Optional[str] = None, date: Optional[str] = None) -> str:
    """
    Analyze heart rate data from Ultrahuman Ring to identify significant drops during the night.

    Args:
        email: Your Ultrahuman account email (uses default from .env if not provided)
        date: Date for analysis in YYYY-MM-DD format (defaults to yesterday if not provided)
    """
    # Use default email from .env if not provided
    if not email:
        if not DEFAULT_EMAIL:
            return "Error: No email provided and no DEFAULT_EMAIL set in .env file."
        email = DEFAULT_EMAIL
        print(f"Using default email from .env: {email}", file=sys.stderr)

    # Use yesterday's date if not provided
    if not date:
        yesterday = datetime.now() - timedelta(days=1)
        date = yesterday.strftime("%Y-%m-%d")

    print(f"Analyzing heart rate for {email} on {date}", file=sys.stderr)

    # Fetch data from Ultrahuman API
    api_data = await fetch_ultrahuman_data(email, date)

    # Check for API error
    if "api_error" in api_data:
        print(f"Found error in API data: {api_data['api_error']}", file=sys.stderr)
        return f"Error fetching data: {api_data['api_error']}"

    try:
        # Check if we have valid data
        if not api_data or "data" not in api_data or "metric_data" not in api_data["data"]:
            print("No valid data structure in API response", file=sys.stderr)
            return f"No valid data returned from Ultrahuman API for {email} on {date}."

        # Extract metrics data
        hr_values, sleep_obj, hrv_values, temp_values = extract_metrics_data(api_data)

        if not hr_values:
            return f"No heart rate data found for {email} on {date}."

        if not sleep_obj:
            return f"Found heart rate data but no sleep data for {email} on {date}."

        # Get sleep metrics
        sleep_metrics = get_sleep_metrics(sleep_obj)

        # Find heart rate drops
        hr_drops = find_heart_rate_drops(hr_values, sleep_obj)

        # Find lowest heart rate
        lowest_hr = find_lowest_heart_rate(hr_values, sleep_obj)

        # Analyze temperature data
        temp_analysis = analyze_temperature_data(temp_values, sleep_obj)

        # Get average HRV if available
        avg_hrv = None
        if "avg_sleep_hrv" in sleep_obj:
            avg_hrv = sleep_obj["avg_sleep_hrv"].get("value")
        else:
            # Try to calculate from HRV values during sleep
            if hrv_values and sleep_obj.get("bedtime_start") and sleep_obj.get("bedtime_end"):
                sleep_hrv = [hrv for hrv in hrv_values if
                            hrv["timestamp"] >= sleep_obj["bedtime_start"] and
                            hrv["timestamp"] <= sleep_obj["bedtime_end"]]
                if sleep_hrv:
                    hrv_sum = sum(hrv["value"] for hrv in sleep_hrv)
                    avg_hrv = int(hrv_sum / len(sleep_hrv))

        # Format results
        result = f"Heart Rate Analysis for {date}:\n\n"
        result += format_analysis_results(sleep_metrics, hr_drops, lowest_hr, temp_analysis, avg_hrv)

        return result

    except Exception as e:
        print(f"Error processing data: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return f"Error processing data: {str(e)}"

if __name__ == "__main__":
    try:
        print("Starting Ultrahuman MCP...", file=sys.stderr)
        mcp.run(transport='stdio')
    except Exception as e:
        print(f"Error in Ultrahuman MCP: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
