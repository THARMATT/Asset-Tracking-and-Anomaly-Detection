# 📦 Asset Tracking and Anomaly Detection System
### Project Guide • Setup • Technology Explained • Weekly Timeline

> **Purpose of this document:** Explain the project in simple language, show how its parts fit together, and help a new team member set it up on a Windows laptop.

---

## 1. Project at a glance

The **Asset Tracking and Anomaly Detection System** is an IoT-oriented project that helps an organization keep track of physical items and identify unusual movement.

Imagine a laptop that should be kept in `SHELF_01`. If the system detects it in `SHELF_03`, it can flag the event as **misplaced**. If an item is scanned at the main gate, the system can check whether its exit is authorized.

### The problem we want to solve

A basic inventory list may tell staff that an item exists, but it may not tell them whether the item is in the correct place or whether its movement is suspicious.

This project aims to help answer four practical questions:

1. **What is the item?** — Identify the asset using an asset ID.
2. **Where should it be?** — Compare its expected location with the detected location.
3. **What happened?** — Save scans and movement events so they can be reviewed.
4. **Does something look wrong?** — Flag events such as misplaced items or unauthorized exits.

**Example:** A registered scanner is expected on `SHELF_03`. A scan reports that it is at `SHELF_01`. The backend checks the event and can record a misplaced-asset result according to the project's rules.

> **Scope note:** The current application has a Flask API, a SQLite database, and a React/Vite frontend. Mosquitto has also been installed and tested for local MQTT messaging. MQTT messages should not be assumed to reach the database automatically until the backend subscriber/bridge is implemented and verified. Wokwi/ESP32 integration is a later integration step.

---


## 2. How the system fits together

```text
Asset scan / simulator / future ESP32 device
                 |
                 | scan event (JSON message)
                 v
          MQTT broker (Mosquitto)
                 |
                 | requires a configured subscriber/bridge
                 v
           Flask backend API
                 |
                 +---- Anomaly rules
                 |
                 +---- SQLite database
                 |
                 v
          React/Vite dashboard
```

The current REST-based path is:

```text
React dashboard  --->  Flask API  --->  Anomaly engine / SQLite
```

The MQTT path is an additional IoT communication route. The broker can deliver messages to MQTT subscribers, but a subscriber/bridge is required to pass those messages into the backend's event-processing code.

### Main project folders

| Folder/file | Simple explanation |
|---|---|
| `backend/app.py` | Starts the Flask web API and defines routes that the frontend can call. |
| `backend/config.py` | Holds shared settings, zone names, event types, and status names. |
| `backend/database.py` | Creates and reads/writes the SQLite tables. |
| `backend/anomaly_engine.py` | Applies the project's event rules to decide whether a scan looks normal or unusual. |
| `backend/init_db.py` | Initializes the database and demo data. |
| `backend/asset_tracking.db` | The local database file containing stored project data. Back it up before deleting or resetting it. |
| `backend/requirements.txt` | Lists the Python packages needed by the backend. |
| `frontend/src/` | The React code that builds the user interface. |
| `frontend/package.json` | Lists frontend packages and commands such as `npm run dev`. |
| `frontend/package-lock.json` | Records exact frontend dependency versions for repeatable installation. |
| `frontend/vite.config.js` | Configures the Vite development server and any API proxy rules. |
| `mosquitto/` | Place for project-specific MQTT configuration, if used. |
| `wokwi/` | Work area for ESP32/Wokwi simulation files. Check which firmware/configuration files actually exist before assuming the simulation is ready. |
| `docs/` | Project documentation and design notes. |
| `Phase1/` | Earlier phase work; keep it unless you have checked that it is no longer needed. |

Folders such as `.venv`, `venv`, `node_modules`, `dist`, and `.pytest_cache` are local environments, installed packages, generated builds, or caches. They are usually recreated on another computer rather than copied.

---

## 4. Technologies used — explained simply

| Technology | What it is in simple words | Why this project uses it |
|---|---|---|
| **Python** | A programming language. | Runs the backend and the event-processing logic. |
| **Flask** | A small Python web framework. | Receives requests from the dashboard and returns data through API routes. |
| **REST API** | A set of URLs that programs use to request or send data. | Lets the frontend ask for assets, events, summaries, and other records. |
| **SQLite** | A database stored in a local file. | Saves assets and events without needing a separate database server. |
| **React** | A JavaScript library for building user interfaces. | Builds the dashboard from reusable screen components. |
| **Vite** | A frontend development server and build tool. | Starts the React app quickly during development. |
| **Node.js and npm** | Node runs JavaScript tools; npm installs frontend packages. | Installs and runs the frontend development tools. |
| **Mosquitto** | An MQTT broker: a central message router. | Lets devices and programs exchange scan messages using MQTT. |
| **MQTT** | A lightweight messaging protocol commonly used in IoT. | Provides a way for a device or simulator to send event messages without directly calling every part of the application. |
| **Paho-MQTT** | A Python library for connecting Python programs to MQTT brokers. | Can be used by a Python backend subscriber, if that integration is added. Installing Mosquitto alone does not install this Python library. |
| **JSON** | A text format for representing structured data. | Carries fields such as asset ID, zone, event type, and timestamp. |
| **PowerShell** | Windows' command-line shell. | Runs setup commands and starts the backend and frontend. |
| **Git and GitHub** | Git records changes; GitHub hosts the repository online. | Helps preserve versions, collaborate, and set up the project on another machine. |
| **Wokwi** | An online microcontroller simulator. | Can simulate supported hardware such as an ESP32 before buying a physical board. |
| **Isolation Forest** | A machine-learning method that flags data points that differ from typical patterns. | A possible future second layer of anomaly detection; only claim it is active if its code, dependencies, and tests are present and working. |
| **Docker** | A tool for packaging an application and its dependencies. | Possible future work to make deployment more repeatable; it is not required for the current local setup. |

### Why not use AWS?

AWS IoT Core is a managed cloud service for connecting IoT devices. It is not required for a local prototype. Mosquitto can provide a local MQTT broker, and Flask plus SQLite can run on the laptop. A cloud platform may be considered later if remote access, managed scaling, or cloud services become necessary.

---

## 5. Important terminology in easy language

### Asset
A physical item the organization wants to track—for example, a laptop, scanner, projector, or lab instrument.

### Asset ID
A unique label for an item, such as `A001`. It helps the system distinguish one item from another.

### Zone
A named area where an asset can be detected, such as `SHELF_01`, `SHELF_02`, or `MAIN_GATE`.

### Expected zone
The location where the item is supposed to be stored.

### Detected zone
The location reported by a scan or device.

### Event
A record of something that happened. For example: “Asset A001 was scanned at SHELF_01 at 10:30.”

### Anomaly
An event that is unusual or violates a rule. It does not automatically mean theft; it means the event needs attention.

### Misplaced asset
An item is detected in a zone different from its expected zone.

### Missing asset
An item expected to be present cannot be found in the relevant check. The exact rule depends on the inventory/audit workflow.

### Authorized exit
An item is leaving through the gate and the system has a valid authorization for that movement.

### Unauthorized exit
An item is detected leaving, but the system does not find the required authorization.

### Unknown asset
The scan refers to an asset ID that is not registered in the system.

### Main-gate verification
A second check at the exit. It is intended to compare the gate scan with the asset's authorization or removal request. This workflow must be implemented and tested before claiming it works end to end.

### IoT (Internet of Things)
Physical devices that collect or exchange information over a network. In this project, a future ESP32 or scanner can send asset-scan events to the software.

### MQTT broker
The central message router. A publisher sends a message to a topic; the broker forwards it to subscribers interested in that topic.

### Publisher
A program or device that sends a message. A simulator could publish a scan event.

### Subscriber
A program that listens for messages on a topic. The backend needs a subscriber/bridge if MQTT messages are to be processed and stored by the application.

### Topic
A named message channel, such as `asset/events`. It helps the broker route a message to the right subscribers.

### Payload
The actual contents of a message. A JSON payload might include the asset ID, zone, and event type.

### REST API endpoint
A URL that performs a specific operation. For example, `GET /api/assets` asks the backend for the asset list.

### Database table
A structured collection of records, similar to a spreadsheet with defined columns.

### Transaction
A group of database operations treated as one unit. If the operation fails, the database can roll it back rather than leaving a partial change.

### Duplicate message / deduplication
Sometimes a message may be delivered more than once. Deduplication means recognizing a repeated event ID so the same event is not processed twice.

### Virtual environment (`.venv`)
A separate Python package environment for this project. It helps keep this project's dependencies separate from other Python projects on the laptop.

### Dependency
A package or tool the project needs in order to run—for example, Flask or React.

### Build
A prepared version of the frontend that can be served or deployed. The development server is normally used while coding.

### Simulator
Software that imitates some behavior of hardware. It is useful for testing before physical devices are available, but simulation results do not prove that real hardware has been tested.

---

## 6. Anomaly statuses — what they mean

The backend's configured status names include the following. The exact result for a particular event depends on the rules and event data.

| Status | Plain-English meaning |
|---|---|
| `NORMAL` | The event follows the expected rules. |
| `MISPLACED` | The asset was detected in a different zone from its expected zone. |
| `MISSING` | The expected item was not detected during a check. |
| `AUTHORIZED_EXIT` | The gate movement is considered authorized. |
| `UNAUTHORIZED_EXIT` | The gate movement lacks the required authorization. |
| `UNAUTHORIZED_REMOVAL` | The event indicates removal that is not permitted by the configured rules. |
| `UNKNOWN_ASSET` | The asset ID is not recognized in the asset records. |
| `MISSING_INVESTIGATION_REQUIRED` | A missing-item condition needs further checking. |
| `INVALID_EVENT` | The event is incomplete, malformed, or fails validation. |

**Important distinction:** A status is the system's result based on the information it receives. It is not proof by itself that a person stole an item. Real deployments need reliable scans, correct asset records, authorization procedures, and human review.

---

## 7. Set up the project on a new Windows laptop

### Before starting

Install these tools:

1. **Python 3.11** — runs the backend.
2. **Node.js LTS** — includes npm, needed for the frontend.
3. **Git for Windows** — needed if you clone from GitHub.
4. **Mosquitto** — optional if you only want to run the REST application; required for local MQTT broker tests.
5. **VS Code** — optional editor.

Open PowerShell and check the installations:

```powershell
python --version
python -m pip --version
node --version
npm --version
git --version
```

Each command should print a version. If a command is not recognized, install that tool and reopen PowerShell.

### Step 1 — Get the repository

If the repository is hosted at the known project URL:

```powershell
Set-Location "$HOME\OneDrive\Desktop"
git clone https://github.com/THARMATT/Asset-Tracking-and-Anomaly-Detection.git
Set-Location ".\Asset-Tracking-and-Anomaly-Detection"
```

If the folder already exists, do not clone it again. Open PowerShell in the existing project root instead. The **project root** is the folder that contains `backend`, `frontend`, and this README.

### Step 2 — Create the Python environment

Run from the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

If PowerShell blocks environment activation, use this temporary permission for the current PowerShell window:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Step 3 — Install backend packages

Still in the project root:

```powershell
python -m pip install -r .\backend\requirements.txt
```

A **package** is reusable code that another program can import. The requirements file lists the Python packages needed by this backend.

### Step 4 — Initialize the database

```powershell
python .\backend\init_db.py
```

The application also initializes the database during startup. Initialization uses the project's current setup logic. Back up any database containing data you want to keep before resetting or replacing it.

### Step 5 — Start the backend

```powershell
python .\backend\app.py
```

Keep this PowerShell window open. The backend normally listens on port `5000`.

Open a **second** PowerShell window and test the API:

```powershell
Invoke-RestMethod "http://127.0.0.1:5000/api/health"
Invoke-RestMethod "http://127.0.0.1:5000/api/assets"
Invoke-RestMethod "http://127.0.0.1:5000/api/summary"
```

If these return responses, the local API is reachable.

### Step 6 — Install frontend packages

Open another PowerShell window:

```powershell
Set-Location "PATH\TO\YOUR\PROJECT\frontend"
npm ci
```

Replace `PATH\TO\YOUR\PROJECT` with the real project folder path. `npm ci` installs the versions recorded in `package-lock.json`.

### Step 7 — Start the frontend

```powershell
npm run dev
```

Open the URL printed in the terminal—often `http://localhost:5173/`. Keep the terminal open while using the dashboard.

### Step 8 — Optional MQTT broker test

If Mosquitto is installed and running, check port `1883`:

```powershell
Test-NetConnection 127.0.0.1 -Port 1883
```

In one terminal, subscribe:

```powershell
mosquitto_sub -h 127.0.0.1 -p 1883 -t "asset/events" -v
```

In another terminal, publish a test message:

```powershell
mosquitto_pub -h 127.0.0.1 -p 1883 -t "asset/events" -m '{"asset_id":"A001","event_type":"TEST","zone":"SHELF_01"}'
```

If the subscriber prints the message, the broker test succeeded. **This test does not prove that the Flask backend saved the event.** That requires a working MQTT subscriber/bridge connected to the backend event-processing path.

---

## 8. API routes currently present in the backend

An API route is a URL that accepts a request and performs a specific action.

| Method | Route | What it does |
|---|---|---|
| `GET` | `/api/health` | Checks whether the backend is responding. |
| `GET` | `/api/summary` | Returns dashboard summary counts. |
| `GET` | `/api/assets` | Lists assets. |
| `GET` | `/api/assets/<asset_id>` | Gets one asset. |
| `PUT` | `/api/assets/<asset_id>` | Updates an asset. |
| `GET` | `/api/events` | Lists recorded events. |
| `POST` | `/api/events` | Submits an event for processing. |
| `GET` | `/api/audits` | Lists inventory audits. |
| `POST` | `/api/audits` | Submits an audit. |
| `GET` | `/api/zones` | Lists configured zones. |
| `GET` | `/api/authorization/<asset_id>` | Reads authorization information for an asset. |
| `PUT` | `/api/authorization/<asset_id>` | Updates authorization information for an asset. |

The route's actual accepted fields and validation rules are defined in `backend/app.py` and `backend/anomaly_engine.py`. Check those files before manually constructing an event request.

---

## 9. Troubleshooting

| Problem | What it means | What to try |
|---|---|---|
| `python` is not recognized | Windows cannot find Python. | Install Python and reopen PowerShell. |
| `ModuleNotFoundError` | A required Python package or local module cannot be found. | Activate `.venv`, install `backend/requirements.txt`, and run from the project root. |
| Port `5000` is already in use | Another process may already be running the backend. | Check existing terminals before starting another copy. |
| Port `1883` is already in use | Mosquitto may already be running as a Windows service. | Check with `Get-Service mosquitto` and `Test-NetConnection 127.0.0.1 -Port 1883`. Do not start a second broker on the same port. |
| Dashboard opens but data is missing | The frontend may not be reaching the backend. | Test `/api/health`; check the browser console, `frontend/.env.development`, `frontend/vite.config.js`, and backend logs. |
| `npm ci` fails | Node/npm may be missing, or the lock file may be inconsistent. | Check `node --version`, `npm --version`, and whether `frontend/package-lock.json` exists. |
| `no such table` database error | The database being used may not have the required schema. | Back up valuable data, run `python .\backend\init_db.py`, and verify the database path in the error/log. |
| MQTT message prints but no dashboard event appears | Broker delivery works, but the app integration may be missing or misconfigured. | Verify the backend subscriber/bridge, topic, payload fields, and event persistence separately. |

---

## 10. Back up and protect the project

### Back up the database

Stop the backend first, then run from the project root:

```powershell
Copy-Item ".\backend\asset_tracking.db" ".\backend\asset_tracking_backup.db"
```

The database can contain asset records, events, and authorization information. Do not delete it unless you are willing to lose those local records or have a verified backup.

### Do not commit local/generated files

Normally, do not commit:

- `.venv/` or `venv/`
- `frontend/node_modules/`
- `frontend/dist/` unless your deployment requires it
- `.pytest_cache/`, `__pycache__/`, or `.pyc` files
- Local database backups
- `.env` files containing credentials
- Real Wi-Fi credentials or device secrets

Keep dependency manifests such as `backend/requirements.txt` and `frontend/package-lock.json` in Git. Before pushing, check:

```powershell
git status
```

Never publish passwords, private tokens, or Wi-Fi credentials to a public repository.

---

## 11. Future improvements

These are possible next steps, not claims that all features are already implemented:

1. **MQTT-to-backend bridge:** Subscribe to `asset/events`, validate messages, and pass them into the existing event-processing code.
2. **Python event simulator:** Generate repeatable test cases for normal scans, misplaced items, unknown assets, and gate events.
3. **Wokwi ESP32 simulation:** Publish test messages from simulated hardware.
4. **Main-gate verification workflow:** Match a gate scan to a valid removal authorization and record the decision.
5. **Automated tests:** Verify expected results for each anomaly scenario.
6. **Machine-learning anomaly detection:** Evaluate whether historical movement data can identify unusual patterns beyond the deterministic rules.
7. **Authentication and permissions:** Restrict who can view assets or approve removals.
8. **Secure remote MQTT:** Add authentication, access controls, and TLS before using a broker across an untrusted network.
9. **Deployment improvements:** Consider Docker or a server database only when there is a clear need.

### Suggested end-to-end acceptance test

The project should be considered connected end to end only when you can demonstrate all of the following:

- [x] The dashboard can load data from the Flask API.
- [x] An event submitted through the API is processed and stored.
- [x] A test event with a wrong zone produces the expected anomaly result.
- [x] A gate event is checked against authorization according to the implemented rules.
- [x] An MQTT message is received by the backend subscriber/bridge.
- [x] The MQTT event is saved once, even if a duplicate message is delivered.
- [x] The dashboard reflects the newly stored event.

### Testing Scenarios with the MQTT Event Publisher

Run realistic IoT telemetry scenarios using the CLI publisher in `simulator/event_publisher.py`:

```powershell
# 1. Normal scan at expected location
backend\venv\Scripts\python.exe simulator\event_publisher.py --scenario normal --count 3

# 2. Misplaced asset anomaly (wrong shelf)
backend\venv\Scripts\python.exe simulator\event_publisher.py --scenario misplaced --count 1

# 3. Security alert: Unauthorized gate exit
backend\venv\Scripts\python.exe simulator\event_publisher.py --scenario unauthorized_exit

# 4. Authorized gate exit
backend\venv\Scripts\python.exe simulator\event_publisher.py --scenario authorized_exit

# 5. Idempotent duplicate message delivery test
backend\venv\Scripts\python.exe simulator\event_publisher.py --scenario duplicate

# 6. Run full demonstration suite (all operational cases sequentially)
backend\venv\Scripts\python.exe simulator\event_publisher.py --scenario all
```

---

## 12. Quick start reference

**Terminal 1 — Backend** (from project root):

```powershell
$env:ENABLE_MQTT="True"
backend\venv\Scripts\python.exe backend\app.py
```

**Terminal 2 — Frontend** (from project root):

```powershell
npm --prefix frontend run dev
```

**Browser:** Open `http://localhost:5173`.

**API health verification:**
```powershell
Invoke-RestMethod "http://127.0.0.1:5000/api/health"
```

**Stop a foreground process:** Press `Ctrl+C` in the terminal running it.

---

### Final reminder

Build and test the system in small steps. First confirm the REST application works, then test MQTT separately, then connect MQTT to the backend, and finally connect a simulator or hardware. This makes errors easier to find and helps you demonstrate exactly which parts are working.
