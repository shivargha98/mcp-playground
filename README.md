# MCP Playground - MLOps Control Center

An MLOps control center that connects **Claude** (via the Model Context Protocol) with **Apache Airflow** and **Google Gemini** to build an automated, multi-LLM financial analyst review pipeline. Analyst stock reviews are ingested, critiqued by Claude, reflected upon by Gemini, and persisted to MongoDB — all orchestrated through MCP tools and an Airflow DAG.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [How It Works](#how-it-works)
- [Project Structure](#project-structure)
- [MCP Server Tools](#mcp-server-tools)
- [Airflow DAG Pipeline](#airflow-dag-pipeline)
- [Data Schemas](#data-schemas)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Running the Project](#running-the-project)
- [Configuration](#configuration)
- [Tech Stack](#tech-stack)

---

## Architecture Overview

```
                          ┌──────────────────────────┐
                          │   Analyst Review (JSON)   │
                          │   lands in stagingArea/   │
                          └────────────┬─────────────┘
                                       │
                          ┌────────────▼─────────────┐
                          │      MCP Server           │
                          │   (mlops_server.py)       │
                          │                           │
                          │  Tool 1: Check staging    │
                          │  Tool 2: Read analyst     │
                          │  Tool 3: Save critique    │
                          │  Tool 4: Trigger Airflow  │
                          └────────────┬─────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
              ▼                        ▼                        ▼
   ┌─────────────────┐   ┌────────────────────┐   ┌────────────────────┐
   │ Claude (via MCP) │   │  doneProcessing/   │   │  Apache Airflow    │
   │ Critiques the    │   │  Saved critique    │   │  DAG trigger via   │
   │ analyst review   │   │  + risk score      │   │  REST API          │
   └─────────────────┘   └────────────────────┘   └─────────┬──────────┘
                                                             │
                          ┌──────────────────────────────────┘
                          │
                          ▼
              ┌──────────────────────────────────────────┐
              │       Airflow DAG: council_review_workflow │
              │                                           │
              │  1. install_dependencies                  │
              │  2. MongoPush1 (analyst + critique → DB)  │
              │  3. gemini_reflection (Gemini critique)   │
              │  4. final_mongodb (full council → DB)     │
              └──────────────────────────────────────────┘
                          │
                          ▼
              ┌──────────────────────┐
              │      MongoDB         │
              │                      │
              │  analyst_reviews.    │
              │    reviews           │
              │    council_review    │
              └──────────────────────┘
```

---

## How It Works

The system implements an **LLM Council** pattern — multiple AI models independently evaluate financial analyst reviews and their assessments are combined for a more robust result.

### Step-by-step workflow

1. **Ingest** — A stock analyst review JSON file is placed into `projectdata/stagingArea/` (simulating a data pipeline drop from something like Apache NiFi).

2. **Detect** — The MCP client (e.g. Claude Desktop or Claude Code) calls `check_nifi_staging_area()` to discover new files waiting to be processed.

3. **Read** — The client calls `read_analyst_file(filename)` to load the analyst review data.

4. **Critique** — Claude reads the analyst review, generates a risk score (1-10) and a 4-5 sentence critique identifying biases, logical fallacies, and gaps. The client then calls `save_initial_critique(risk_score, critique_summary)` to persist the output.

5. **Reflect** — The client calls `start_llm_council_reflection()` which triggers an Airflow DAG via its REST API. The DAG runs a four-stage pipeline:
   - Pushes the analyst review + Claude's critique to MongoDB
   - Sends the review to **Google Gemini 2.0 Flash** for an independent senior analyst reflection
   - Combines all three perspectives (analyst, Claude, Gemini) into a final council review document and stores it in MongoDB

---

## Project Structure

```
mcp-playground/
├── mlops_server.py              # FastMCP server — exposes 4 tools
├── test.py                      # Quick Airflow API auth test
├── pyproject.toml               # Python project config & dependencies
├── uv.lock                      # Dependency lock file (uv)
├── .python-version              # Python 3.13
├── .gitignore
├── README.md
│
├── projectdata/                 # Data directory
│   ├── stagingArea/             # Incoming analyst reviews (input)
│   ├── doneProcessing/          # Claude critique outputs
│   └── tobeProcessed/           # Processing queue
│
└── airflow_as_mcp/              # Airflow service
    ├── docker-compose.yaml      # Full Airflow cluster (CeleryExecutor)
    ├── .env                     # Airflow UID + API keys
    ├── config/
    │   └── airflow.cfg          # Airflow configuration
    ├── dags/
    │   └── reflection_dag.py    # Council review DAG
    ├── logs/                    # DAG execution logs
    └── plugins/                 # Custom Airflow plugins
```

---

## MCP Server Tools

The FastMCP server (`mlops_server.py`) exposes four tools that an MCP-compatible client can call:

### Tool 1: `check_nifi_staging_area`

Scans the staging directory for new `.json` files ready for processing.

| Parameter | Type | Description |
|-----------|------|-------------|
| *(none)* | — | — |

**Returns:** A string listing found files, or `"No Files to process"`.

### Tool 2: `read_analyst_file`

Reads and returns the contents of a specific analyst review file.

| Parameter | Type | Description |
|-----------|------|-------------|
| `filename` | `str` | Name of the JSON file in `stagingArea/` |

**Returns:** A dictionary containing the analyst review data.

### Tool 3: `save_initial_critique`

Saves Claude's risk assessment and critique to the `doneProcessing/` directory as a timestamped JSON file.

| Parameter | Type | Description |
|-----------|------|-------------|
| `risk_score` | `int` | Risk score (1-10) assigned by Claude |
| `critique_summary` | `str` | 4-5 sentence critique of the analyst review |

**Returns:** Success/error message with the saved file path.

### Tool 4: `start_llm_council_reflection`

Triggers the Airflow DAG (`council_review_workflow`) via the Airflow REST API. Authenticates, creates a unique DAG run ID, and starts the pipeline with a 30-second delay.

| Parameter | Type | Description |
|-----------|------|-------------|
| *(none)* | — | — |

**Returns:** The DAG run ID on success, or an error message.

---

## Airflow DAG Pipeline

**DAG ID:** `council_review_workflow`
**Schedule:** Manual trigger only (via MCP Tool 4)
**Tags:** `mlops`, `gemini`, `mongo`

```
install_dependencies ──> MongoPush1 ──> gemini_reflection ──> final_mongodb
```

| Task | Type | Description |
|------|------|-------------|
| `install_dependencies` | BashOperator | Installs `pymongo`, `langchain-google-genai`, `langchain` in the Airflow worker |
| `MongoPush1` | PythonOperator | Reads the analyst review and Claude's critique, combines them into a single document, and inserts into `analyst_reviews.reviews` collection |
| `gemini_reflection` | PythonOperator | Sends the analyst review to Google Gemini 2.0 Flash with a senior analyst prompt. Gemini critiques the review for logical fallacies, biases, and missed points |
| `final_mongodb` | PythonOperator | Pulls the Gemini reflection via XCom, combines it with the analyst review and Claude's critique, and inserts the full council review into `analyst_reviews.council_review` collection |

---

## Data Schemas

### Input: Analyst Review (`stagingArea/`)

```json
{
  "stock_name": "Tata Consultancy Services Ltd",
  "stock_ticker_nse": "TCS",
  "stock_price": 3850.75,
  "analyst_review": "The analyst believes the stock is well positioned due to...",
  "analyst_rating": "BUY",
  "analyst_upside_percentage": 9.1
}
```

### Output: Claude Critique (`doneProcessing/`)

```json
{
  "meta": {
    "timestamp": "2026-01-21T17:49:52.117612"
  },
  "audit": {
    "risk_score": 4,
    "critique_summary": "The analyst's BUY recommendation appears conservative given the modest 9.1% upside..."
  }
}
```

### MongoDB: Final Council Review (`analyst_reviews.council_review`)

```json
{
  "analyst_review": { "...analyst review JSON..." },
  "claude_critique": { "...Claude critique JSON..." },
  "gemini_reflect": "Senior analyst reflection text from Gemini...",
  "timestamp": "2026-01-21T17:50:30.123456"
}
```

---

## Prerequisites

- **Python** 3.13+
- **uv** (Python package manager) — [install guide](https://docs.astral.sh/uv/)
- **Docker** & **Docker Compose** (for the Airflow cluster)
- **MongoDB** instance (local or Atlas)
- **Google API Key** (for Gemini 2.0 Flash)
- An **MCP-compatible client** (Claude Desktop, Claude Code, etc.)

---

## Setup & Installation

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/mcp-playground.git
cd mcp-playground
```

### 2. Install Python dependencies

```bash
uv sync
```

### 3. Configure environment variables

Create or update `airflow_as_mcp/.env`:

```env
AIRFLOW_UID=50000
GOOGLE_API_KEY=<your-google-api-key>
```

Set the following as **Airflow Variables** (via the Airflow UI or CLI once the cluster is running):

| Variable | Description |
|----------|-------------|
| `MONGO_URI` | MongoDB connection string (e.g. `mongodb+srv://user:pass@cluster.mongodb.net/`) |
| `GOOGLE_API_KEY` | Google API key for Gemini |

### 4. Start the Airflow cluster

```bash
cd airflow_as_mcp
docker compose up -d
```

This spins up:
- **PostgreSQL 16** — Airflow metadata database
- **Redis 7.2** — Celery message broker
- **Airflow API Server** — REST API on port `8080`
- **Airflow Scheduler** — DAG scheduling
- **Airflow DAG Processor** — DAG parsing
- **Airflow Worker** — Celery task executor
- **Airflow Triggerer** — Event-based triggers

Wait for initialization to complete, then access the Airflow UI at `http://localhost:8080` (default credentials: `airflow` / `airflow`).

### 5. Unpause the DAG

In the Airflow UI, find `council_review_workflow` and toggle it to **active** (unpaused).

---

## Running the Project

### Start the MCP server

```bash
uv run mlops_server.py
```

The server starts in `stdio` transport mode, ready for an MCP client to connect.

### Connect from Claude Desktop

Add the server to your Claude Desktop MCP config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "mlops_control_center": {
      "command": "uv",
      "args": ["run", "mlops_server.py"],
      "cwd": "/path/to/mcp-playground"
    }
  }
}
```

### Typical conversation flow

Once connected, Claude can be instructed to run the full pipeline:

> "Check the staging area for new analyst reviews, read the file, critique it with a risk score, save your critique, and then trigger the LLM council reflection pipeline."

Claude will call the four MCP tools in sequence to execute the entire workflow.

---

## Configuration

### Directory paths

The MCP server uses hardcoded paths in `mlops_server.py`. Update these to match your environment:

```python
DIR = 'D:/mcp-playground/projectdata/'
STAGING_DIR = 'D:/mcp-playground/projectdata/stagingArea/'
DRAFT_DIR = "D:/mcp-playground/projectdata/doneProcessing/"
```

### Airflow data path

Inside the Airflow containers, the project data is mounted at:

```python
BASE_DATA_PATH = '/opt/airflow/projectdata/'
```

This is configured in `docker-compose.yaml` via the volume mount:

```yaml
- ../projectdata:/opt/airflow/projectdata
```

### Docker services

| Service | Port | Purpose |
|---------|------|---------|
| Airflow API Server | `8080` | REST API & Web UI |
| Flower (optional) | `5555` | Celery monitoring (`docker compose --profile flower up`) |

---

## Tech Stack

| Component | Technology | Role |
|-----------|-----------|------|
| MCP Server | [FastMCP](https://github.com/jlowin/fastmcp) | Exposes tools to MCP clients |
| LLM (Critique) | Claude (via MCP) | Initial risk scoring and analyst review critique |
| LLM (Reflection) | Google Gemini 2.0 Flash | Independent senior analyst reflection |
| Orchestration | Apache Airflow 3.1.6 | DAG-based pipeline execution |
| Task Queue | Celery + Redis 7.2 | Distributed task execution |
| Metadata DB | PostgreSQL 16 | Airflow metadata storage |
| Data Store | MongoDB | Persistent storage for reviews and council outputs |
| Package Manager | uv | Python dependency management |
| Containerization | Docker Compose | Airflow cluster deployment |
| Framework | LangChain | Gemini prompt chaining |
