# Setting Up MCP Server with Python and uv

This guide provides detailed instructions for setting up and running the Model Context Protocol (MCP) server using Python and uv on a new computer. This setup enables custom tools to work with Claude Desktop.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Connecting to Claude Desktop](#connecting-to-claude-desktop)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Before beginning, ensure you have:

- A computer running macOS, or Linux
- Administrative privileges
- Python 3.8+ installed
- Git installed (for cloning the repository)
- Claude Desktop application installed

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/anthropic/model-control-protocol.git
cd model-control-protocol
```

### Step 2: Set Up Python Environment with uv

uv is a much faster alternative to pip for Python package management. Here's how to set up your environment with uv:

```bash
# Install uv if you don't have it yet
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create a virtual environment
uv venv

# Activate the virtual environment
source .venv/bin/activate
```

### Step 3: Install Dependencies with uv
```bash
uv pip install -r requirements.txt
```

## Configuration

### Step 1: Create Environment Variables
Rename sample.env to .env

Request for your partner API key from UH. Once you have it, the documentation on how to use it is available here - https://www.notion.so/ultrahumanapp/UltraSignal-API-Documentation-5f32ec15ef6b4fa5bc8249f7b875d212?pvs=4

Replace `your_partner_api_token` with your UH partners API key and `your_ultrahuman_user_email` with your Ultrahuman user email.

### Step 2: Configure Tools
Open ~/Library/Application\ Support/Claude/claude_desktop_config.json or create claude_desktop_config.json in this path if it doesn't exist.

Type in ```which uv``` to find your uv_path.

And paste in the following:
```bash
{
    "mcpServers": {
        "uh_mcp": {
            "command": "uv_path",
            "args": [
                "--directory",
                "/ABSOLUTE/PATH/TO/PARENT/FOLDER/uh-mcp",
                "run",
                "uh_mcp.py"
            ]
        }
    }
}
EOL
```

Restart claude desktop app whenever you make changes to this config.

## Connecting to Claude Desktop
1. Open Claude Desktop application
2. The MCP server should start showing up on the hammer icon

When successful, Claude Desktop will confirm the connection to your MCP server.

## Troubleshooting

### Package Installation Issues

If you encounter issues with uv:

```bash
# Update uv to the latest version
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or try installing dependencies individually
uv pip install requests
uv pip install python-dotenv
# etc.
```
