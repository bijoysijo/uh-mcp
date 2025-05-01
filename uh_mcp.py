from typing import Optional
import sys
import os
from datetime import datetime, timedelta
import httpx
from mcp.server.fastmcp import FastMCP
import json

# Print debug information
script_dir = os.path.dirname(os.path.abspath(__file__))
print(f"Script directory: {script_dir}", file=sys.stderr)
print(f"Current working directory: {os.getcwd()}", file=sys.stderr)
print(f"Files in current directory: {os.listdir()}", file=sys.stderr)

# Initialize FastMCP server
mcp = FastMCP("ultrahuman")

# Get configuration from .env file or use defaults
try:
    from dotenv import load_dotenv
    load_dotenv()

    # Read the .env file directly to check its content
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            env_content = f.read()
        print(f"Content of .env file: {env_content.replace('{', '{{').replace('}', '}}')}", file=sys.stderr)
except Exception as e:
    print(f"Error reading .env: {e}", file=sys.stderr)

# Constants - with fallbacks
ULTRAHUMAN_API_BASE = "https://partner.ultrahuman.com/api/v1"
AUTH_TOKEN = os.getenv("ULTRAHUMAN_API_TOKEN")
DEFAULT_EMAIL = os.getenv("DEFAULT_EMAIL", "bijoysijo21@gmail.com")

print("Using email: " + DEFAULT_EMAIL, file=sys.stderr)

if not AUTH_TOKEN:
    print("WARNING: ULTRAHUMAN_API_TOKEN not set", file=sys.stderr)

@mcp.tool()
async def analyze_night_heart_rate(email: Optional[str] = None, date: Optional[str] = None) -> str:
    """
    Analyze heart rate data from Ultrahuman Ring.

    Args:
        email: Your Ultrahuman account email (uses default if not provided)
        date: Date for analysis in YYYY-MM-DD format (defaults to yesterday if not provided)
    """
    # Use default email if not provided
    if not email:
        email = DEFAULT_EMAIL
        print(f"Using default email: {email}", file=sys.stderr)

    # Use yesterday's date if not provided
    if not date:
        yesterday = datetime.now() - timedelta(days=1)
        date = yesterday.strftime("%Y-%m-%d")

    print(f"Analyzing heart rate for {email} on {date}", file=sys.stderr)

    try:
        # Construct API request
        url = f"{ULTRAHUMAN_API_BASE}/metrics"
        headers = {"Authorization": AUTH_TOKEN}
        params = {"email": email, "date": date}

        print(f"Making API request to {url}", file=sys.stderr)

        # Make API request
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params, timeout=30.0)
            status_code = response.status_code
            print(f"Response status: {status_code}", file=sys.stderr)

            if status_code != 200:
                return f"Error: API returned status code {status_code}"

            # Basic response analysis
            data = response.json()
            metric_count = len(data.get("data", {}).get("metric_data", []))

            return f"Successfully retrieved {metric_count} metrics for {email} on {date}."

    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return f"Error analyzing data: {str(e)}"

if __name__ == "__main__":
    try:
        print("Starting Ultrahuman MCP...", file=sys.stderr)
        mcp.run(transport='stdio')
    except Exception as e:
        print(f"Error in Ultrahuman MCP: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
