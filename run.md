# Asset Tracking and Anomaly Detection System

An IoT-oriented asset management prototype that tracks registered
assets, checks their detected location against their expected zone,
records events, and identifies anomalies such as misplaced assets,
missing assets, unknown assets, and authorized or unauthorized exits.

This repository currently contains a Flask REST API, a SQLite database,
and a React/Vite frontend. Mosquitto is available as the local MQTT
broker for the IoT integration stage. The Wokwi folder may be used for
ESP32 simulation work as firmware/configuration files are added.

> **Important implementation note:** The REST API and database are the
> currently verified application path. Do not assume MQTT messages are
> automatically forwarded into the backend unless the MQTT
> subscriber/bridge has been implemented and started. The MQTT broker
> can be tested independently using the commands in this guide.

------------------------------------------------------------------------

## 1. Project features

-   Register and view assets.
-   Store each asset's expected zone and authorization information.
-   Record scan events through the REST API.
-   Evaluate events using the anomaly engine.
-   Identify conditions represented by the backend, including:
    -   `NORMAL`
    -   `MISPLACED`
    -   `MISSING`
    -   `AUTHORIZED_EXIT`
    -   `UNAUTHORIZED_EXIT`
    -   `UNAUTHORIZED_REMOVAL`
    -   `UNKNOWN_ASSET`
    -   `MISSING_INVESTIGATION_REQUIRED`
    -   `INVALID_EVENT`
-   Store assets, events, zones, authorizations, and audit records in
    SQLite.
-   Provide API endpoints for the frontend.
-   Use a local MQTT broker (Mosquitto) as the planned/available
    messaging layer for IoT devices or simulators.

The exact anomaly result depends on the event payload, asset
registration, expected zone, event type, and authorization
configuration.

## 2. Architecture

``` text
React + Vite frontend
        |
        | HTTP requests (/api/...)
        v
Flask REST API (Python)
        |
        +---- Anomaly engine
        |
        +---- SQLite database
        |
        +---- (MQTT integration when subscriber/bridge is configured)
                       ^
                       |
                Mosquitto broker
                       ^
                       |
            IoT device / simulator
```

### Main folders

``` text
Asset  Tracking system/
├── backend/
│   ├── app.py                 # Flask API application
│   ├── config.py              # Application settings, zones, statuses, event types
│   ├── database.py            # SQLite schema and database operations
│   ├── anomaly_engine.py      # Event validation and anomaly evaluation
│   ├── init_db.py             # Database initialization utility
│   ├── requirements.txt       # Python dependencies
│   └── asset_tracking.db      # Local SQLite database (may be created on first run)
├── frontend/
│   ├── src/                   # React application source
│   ├── package.json           # Node dependencies and scripts
│   ├── package-lock.json      # Locked JavaScript dependency versions
│   ├── vite.config.js
│   └── .env.development       # Development environment configuration
├── docs/                      # Project documentation
├── mosquitto/                 # Project-related Mosquitto files, if any
├── wokwi/                     # Wokwi/ESP32 work area
├── Phase1/                    # Earlier phase files
├── .venv/                     # Local Python environment (do not copy to another PC)
└── README.md
```

Some folders/files may differ as development continues. The `.venv`,
`venv`, `node_modules`, cache folders, and local database are
machine/runtime artifacts and should not be treated as portable source
code.

## 3. Requirements for a new Windows machine

Install the following before running the project:

1.  **Git for Windows** (optional, but recommended for cloning the
    repository).
2.  **Python 3.11** (recommended to match the development environment).
3.  **Node.js LTS**, which includes npm.
4.  **Mosquitto MQTT broker** only if you need to test MQTT messaging
    locally.
5.  **A code editor** such as Visual Studio Code (optional).
6.  **A modern browser** for the frontend.

Check installations in PowerShell:

``` powershell
python --version
python -m pip --version
node --version
npm --version
git --version
```

Python should report Python 3.11.x (or another version compatible with
the installed dependencies). Node and npm should both print version
numbers. If a command is not recognized, install that tool and reopen
PowerShell.

## 4. Get the project on the new machine

### Option A --- Clone from GitHub

Open PowerShell and move to the directory where you want the project:

``` powershell
Set-Location "$HOME\OneDrive\Desktop"
```

Clone the repository:

``` powershell
git clone https://github.com/THARMATT/Asset-Tracking-and-Anomaly-Detection.git
Set-Location ".\Asset-Tracking-and-Anomaly-Detection"
```

If the repository URL or repository name changes, use the current clone
URL shown on GitHub.

### Option B --- Copy the project folder

Copy the project folder to the new machine, then open PowerShell in the
copied project root. The project root is the directory containing
`backend`, `frontend`, `docs`, and this `README.md`.

**Do not copy virtual environments** (`.venv` or `venv`) or
`frontend\node_modules` from the old computer. They should be recreated
on the new machine.

## 5. Configure the Python backend

Run these commands from the project root.

### Step 1: Create a virtual environment

``` powershell
python -m venv .venv
```

### Step 2: Activate it

``` powershell
.\.venv\Scripts\Activate.ps1
```

The prompt should normally show `(.venv)` at the beginning.

If PowerShell blocks activation because of the execution policy, use
this temporary setting for the current PowerShell session:

``` powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

This setting applies only to the current PowerShell process.
Alternatively, run the environment's Python directly without activating
it:

``` powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

### Step 3: Install backend dependencies

``` powershell
python -m pip install --upgrade pip
python -m pip install -r .\backend\requirements.txt
```

The current backend requirements include Flask, Flask-Cors,
python-dotenv, and pytest. If MQTT integration is added to the backend
later, install the MQTT library specified by the updated
`requirements.txt`; do not assume it is installed just because Mosquitto
is installed.

### Step 4: Initialize the database

The application initializes its database when `backend\app.py` creates
the Flask app. You can also run the initialization utility explicitly:

``` powershell
python .\backend\init_db.py
```

The database is configured in `backend\config.py` and normally stored
at:

``` text
backend\asset_tracking.db
```

Initialization seeds demo data using insert-if-missing behavior. If the
database already contains important records, back it up before running
database maintenance or deleting it.

### Step 5: Start the backend

``` powershell
python .\backend\app.py
```

Keep this terminal open. The backend normally listens on port `5000`.

Open a **second PowerShell window** for the checks below. Do not start a
second copy of the backend on the same port.

### Step 6: Verify the API

Health endpoint:

``` powershell
Invoke-RestMethod "http://127.0.0.1:5000/api/health"
```

Asset list:

``` powershell
Invoke-RestMethod "http://127.0.0.1:5000/api/assets"
```

Summary:

``` powershell
Invoke-RestMethod "http://127.0.0.1:5000/api/summary"
```

The endpoints should return JSON. If they do, the backend is running and
reachable locally.

## 6. Configure and start the React frontend

Open another PowerShell terminal and move to the project root. Keep the
backend terminal running.

``` powershell
Set-Location "PATH\TO\YOUR\PROJECT"
Set-Location .\frontend
```

Replace `PATH\TO\YOUR\PROJECT` with the actual path on the new machine.
For example, if the project is on the Desktop, use its real folder path.

Install JavaScript dependencies:

``` powershell
npm ci
```

`npm ci` uses `package-lock.json` to install the locked dependencies. If
the repository does not contain a `package-lock.json`, use `npm install`
instead.

Start the development server:

``` powershell
npm run dev
```

Vite prints a local URL, commonly:

``` text
http://localhost:5173/
```

Open the exact URL printed in the terminal. Keep this terminal open
while using the frontend.

### Frontend environment configuration

Check `frontend\.env.development` and `frontend\.env.production` if the
frontend cannot reach the API. Development API requests should target
the local Flask server or use the proxy configured in `vite.config.js`.

Do not place passwords, private tokens, or other secrets in frontend
environment variables. Values embedded in a browser frontend are not
secret.

### Optional production build check

Stop the frontend dev server with `Ctrl+C`, then run:

``` powershell
npm run build
```

A successful build creates/updates the `frontend\dist` directory. To
preview the built frontend:

``` powershell
npm run preview
```

Use the URL printed by Vite.

## 7. Run the whole application

For normal local development, use two terminals:

**Terminal 1 --- Backend**

``` powershell
Set-Location "PATH\TO\YOUR\PROJECT"
.\.venv\Scripts\Activate.ps1
python .\backend\app.py
```

**Terminal 2 --- Frontend**

``` powershell
Set-Location "PATH\TO\YOUR\PROJECT\frontend"
npm run dev
```

Then open the frontend URL printed by Vite, usually
`http://localhost:5173/`.

The backend API is usually available at `http://127.0.0.1:5000`.

## 8. Mosquitto MQTT broker (optional for REST-only use)

Mosquitto is separate from the Flask API. Installing the broker does not
automatically connect MQTT messages to the database; the application
needs an MQTT subscriber/bridge to receive messages and pass them into
the backend's event-processing path.

### Step 1: Install Mosquitto

Install Mosquitto on the new machine using the official Mosquitto
website and follow its Windows installation instructions. During
installation, note the executable location. A common location is:

``` text
C:\Program Files\mosquitto\
```

Open a new PowerShell window after installation and check:

``` powershell
mosquitto -h
mosquitto_pub -h
mosquitto_sub -h
```

If the commands are not recognized, use the full path to the executable
or add the Mosquitto installation directory to `PATH`.

### Step 2: Check whether the broker is running

If Mosquitto was installed as a Windows service:

``` powershell
Get-Service mosquitto
```

If it is running, **do not start another broker on the same port**. The
default MQTT port is `1883`.

Check the local port:

``` powershell
Test-NetConnection 127.0.0.1 -Port 1883
```

If the service is not installed/running, follow the installation's
service instructions or start the broker using the installed executable
and configuration. Do not run a second instance if port 1883 is already
occupied.

### Step 3: Test MQTT publish/subscribe locally

Open **Terminal A** and subscribe to a test topic:

``` powershell
mosquitto_sub -h 127.0.0.1 -p 1883 -t "asset/events" -v
```

Leave it running. Open **Terminal B** and publish a test message:

``` powershell
mosquitto_pub -h 127.0.0.1 -p 1883 -t "asset/events" -m '{"asset_id":"A001","event_type":"TEST","zone":"SHELF_01"}'
```

Terminal A should display the topic and message. This verifies the
broker, not the complete asset application. A separate backend MQTT
subscriber is needed to persist such messages as application events.

### Security note

The commands above are for local development. Do not expose port `1883`
to the public internet or use an unauthenticated broker in a real
deployment. Configure authentication, access-control lists, TLS, and
firewall rules before connecting devices across an untrusted network.

## 9. API endpoints

The Flask app currently defines these routes:

  ---------------------------------------------------------------------------------
  Method                  Endpoint                          Purpose
  ----------------------- --------------------------------- -----------------------
  `GET`                   `/api/health`                     Check backend health

  `GET`                   `/api/summary`                    Get dashboard summary
                                                            counts

  `GET`                   `/api/assets`                     List assets

  `GET`                   `/api/assets/<asset_id>`          Get one asset

  `PUT`                   `/api/assets/<asset_id>`          Update an asset

  `GET`                   `/api/events`                     List recorded events

  `POST`                  `/api/events`                     Submit an event for
                                                            processing

  `GET`                   `/api/audits`                     List inventory audits

  `POST`                  `/api/audits`                     Submit an audit

  `GET`                   `/api/zones`                      List configured zones

  `GET`                   `/api/authorization/<asset_id>`   Read an asset's
                                                            authorization

  `PUT`                   `/api/authorization/<asset_id>`   Update an asset's
                                                            authorization
  ---------------------------------------------------------------------------------

The exact request body fields and validation rules are defined by
`backend\app.py` and `backend\anomaly_engine.py`. Use those files as the
source of truth when creating API requests or integrating a device.

### Test an event through the REST API

Use the frontend where possible, because it sends requests using the
application's expected format. If testing manually, first inspect the
event payload handling in `backend\app.py` and
`backend\anomaly_engine.py`; do not assume that `zone` and
`detected_zone` are interchangeable in every route.

A simple health check from PowerShell:

``` powershell
Invoke-RestMethod "http://127.0.0.1:5000/api/health"
```

## 10. Demo data and database handling

The SQLite database is normally located at:

``` text
backend\asset_tracking.db
```

Demo assets currently include IDs such as `A001` through `A005` and
zones such as `SHELF_01`, `SHELF_02`, `SHELF_03`, and `MAIN_GATE`. The
exact rows may change as you edit the database.

### Back up the database

Stop the backend first, then run from the project root:

``` powershell
Copy-Item ".\backend\asset_tracking.db" ".\backend\asset_tracking_backup.db"
```

Keep the backup outside version control if it contains real inventory or
operational information.

### Resetting data

Do not delete the database casually. It may contain events, asset edits,
authorization settings, and audits. If you need a clean demo database,
stop the backend, back up the database, and follow the project's current
database initialization/reset procedure. Avoid manually deleting tables.

## 11. Running tests

The backend requirements include `pytest`. If tests exist in the
repository, run from the project root with the virtual environment
activated:

``` powershell
python -m pytest
```

If pytest reports that no tests were collected, check whether test files
have been added; that message does not itself prove the application is
broken.

## 12. Common problems and fixes

### `python` is not recognized

Install Python and select the option that adds Python to `PATH`, or use
the full path to `python.exe`. Reopen PowerShell after installation.

### `ModuleNotFoundError`

Activate the project's virtual environment and install requirements:

``` powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\backend\requirements.txt
```

Run commands from the project root unless a command explicitly says to
enter `frontend`.

### `Address already in use` on port 5000

Another process may already be running the backend. Check the existing
terminal before launching another copy. If necessary, identify the
process using port 5000 and stop it only if you know it belongs to this
project.

### Port 1883 is already in use

Mosquitto may already be running as a Windows service. Check it with:

``` powershell
Get-Service mosquitto
Test-NetConnection 127.0.0.1 -Port 1883
```

Do not start a second broker on the same port.

### Frontend loads but API data does not appear

1.  Confirm the Flask terminal is still running.
2.  Test `http://127.0.0.1:5000/api/health`.
3.  Check the frontend environment files and `frontend\vite.config.js`.
4.  Check browser developer tools for the failing request and its URL.
5.  Check the backend terminal for error messages.

### `npm ci` fails

Confirm Node.js and npm are installed, and that
`frontend\package-lock.json` is present. If the lock file is missing or
inconsistent, use `npm install` and commit the updated lock file if
appropriate.

### Database error such as `no such table`

Make sure the backend is using the intended database path and run:

``` powershell
python .\backend\init_db.py
```

Back up the database first if it contains data you want to preserve. If
the problem persists, inspect the traceback and the path printed by the
backend; multiple copies of the project can lead to opening a different
database than expected.

### MQTT test works but no event appears in the dashboard

The publish/subscribe test only confirms Mosquitto. Confirm that an MQTT
subscriber/bridge is implemented, configured for the same broker and
topic, and forwarding validated messages to the event-processing path.
MQTT does not automatically write to SQLite.

## 13. Git and files that should not be committed

The following are generally local/generated files and should not be
committed:

-   `.venv/` and `venv/`
-   `frontend/node_modules/`
-   `frontend/dist/` (unless your deployment specifically requires built
    assets)
-   `.pytest_cache/`
-   Python `__pycache__/` folders and `.pyc` files
-   Local database backups
-   `.env` files containing private credentials

Keep `requirements.txt` and `frontend/package-lock.json` in Git so
another machine can reproduce the dependencies. Commit `.env.example`
templates, but never commit real credentials or tokens.

Before pushing to GitHub, inspect:

``` powershell
git status
```

If a secret was committed, removing it from the latest commit may not be
enough; rotate/revoke the secret and clean the repository history as
appropriate.

## 14. Suggested first-run checklist

On a fresh Windows machine:

-   [ ] Install Python 3.11.
-   [ ] Install Node.js LTS.
-   [ ] Clone/copy the repository.
-   [ ] Create and activate `.venv`.
-   [ ] Install `backend\requirements.txt`.
-   [ ] Initialize the database if needed.
-   [ ] Start `python backend\app.py`.
-   [ ] Confirm `/api/health`, `/api/assets`, and `/api/summary`.
-   [ ] Run `npm ci` inside `frontend`.
-   [ ] Start `npm run dev`.
-   [ ] Open the URL printed by Vite.
-   [ ] If testing MQTT, start/check Mosquitto and run the
    publish/subscribe test.
-   [ ] Verify the MQTT-to-backend bridge separately before expecting
    MQTT events to appear in the dashboard.

## 15. Stopping the application

In each terminal running a development process, press:

``` text
Ctrl+C
```

This stops the foreground Flask or Vite process. Mosquitto may be
running as a Windows service and may continue running after the
terminals close.

## 16. Development status and next integration step

The local web application uses Flask, SQLite, and React/Vite. Mosquitto
can provide local MQTT messaging, and Wokwi can be used to simulate
ESP32 hardware without buying a physical board.

For an end-to-end IoT demonstration, the next integration milestone is
to connect a device/simulator publisher to Mosquitto, implement or
configure the MQTT subscriber in the backend, validate incoming message
fields, and forward each valid message into the existing
event-processing/database flow. Then verify that a published message
creates a database event and updates the dashboard. Keep the existing
REST API as a working test path while adding MQTT.

------------------------------------------------------------------------

## Quick start summary

From the project root, in **Terminal 1**:

``` powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\backend\requirements.txt
python .\backend\app.py
```

In **Terminal 2**:

``` powershell
Set-Location ".\frontend"
npm ci
npm run dev
```

Open the local URL printed by Vite. In a third terminal, verify:

``` powershell
Invoke-RestMethod "http://127.0.0.1:5000/api/health"
```

For MQTT, use the separate Mosquitto section above and remember that
broker delivery and application event persistence are two different
checks.
