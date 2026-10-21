# IoT-Based Smart Asset Tracking and Unauthorized Movement Detection System

## 1. Project Overview

The IoT-Based Smart Asset Tracking and Unauthorized Movement Detection System is designed to monitor physical assets in environments such as warehouses, storage rooms, and malls.

The system aims to identify misplaced assets, detect assets that cannot be found, monitor asset movement, and verify whether an asset is authorized to leave through the main gate.

The proposed system combines IoT tracking devices, wireless communication, a Python backend, a database, and a dashboard to improve asset visibility and security.

The project is being developed incrementally, starting with a software prototype and later integrating physical IoT hardware.

**Current development stage:** Phase 2 — Software Prototype.

**Current implementation mode:** Software simulation using Python and SQLite.

---

## 2. Problem Statement

Warehouses, malls, and storage facilities contain many physical assets that must remain in their assigned locations or be moved only with authorization.

Manual asset monitoring can be time-consuming and may not identify misplaced or missing items immediately. Unauthorized removal may also go unnoticed if exit verification is not performed properly.

The project proposes an automated asset monitoring system that records asset detections, compares detected locations with expected locations, and checks exit authorization at the main gate.

The system will generate status reports and security alerts to help identify unusual asset movements.

---

## 3. Objectives

The primary objectives are:

1. Assign a unique identifier to each registered asset.
2. Maintain expected asset locations.
3. Record asset detection events.
4. Identify assets detected in unexpected locations.
5. Identify assets that have not been detected within a defined checking period.
6. Verify exit authorization at the main gate.
7. Identify unauthorized exit events.
8. Maintain asset movement and event history.
9. Display asset information and alerts through a dashboard.
10. Integrate IoT tracking hardware and wireless communication in later development phases.

---

## 4. Proposed Solution

Each asset will have a unique ID associated with a tracking tag or device.

Tracking readers or gateways installed in predefined zones will detect the asset and send tracking information to the system.

The backend will compare the detected location with the asset's expected location.

When an asset reaches the main gate, the system will check its exit authorization.

Based on the available tracking events and authorization information, the system will classify the asset status and record the result.

### Example

Suppose a laptop is expected to be at SHELF_01.

- If detected at SHELF_01, it is classified as NORMAL.
- If detected at SHELF_03, it is classified as MISPLACED.
- If not detected within the configured checking period, it can be flagged for investigation.
- If detected at MAIN_GATE with valid exit permission, it is classified as AUTHORIZED_EXIT.
- If detected at MAIN_GATE without valid exit permission, it is classified as UNAUTHORIZED_EXIT.

A missing asset is not automatically considered stolen. Unauthorized removal is a stronger conclusion when supported by gate-detection and authorization evidence.

---

## 5. System Architecture

The planned system architecture is:

    Physical Asset
          |
          v
    RFID or BLE Tracking Tag
          |
          v
        ESP32
          |
          v
     Wi-Fi Communication
          |
          v
       MQTT Broker
          |
          v
     Python Backend
          |
          v
      Anomaly Engine
          |
          v
       SQLite Database
          |
          v
    Streamlit Dashboard
          |
          v
     Reports and Alerts

### Component Description

**1. Tracking Tag**

An RFID tag or BLE beacon will be associated with an asset.

**2. ESP32**

The ESP32 will act as an IoT controller or gateway. The exact reader or receiver hardware will depend on the selected tracking technology.

**3. Wi-Fi**

Wi-Fi will provide network connectivity between the ESP32 and the backend communication service.

**4. MQTT**

MQTT will be used to transfer tracking events from IoT devices to the backend.

**5. Python Backend**

Python will process tracking information and coordinate the database and detection logic.

**6. Anomaly Engine**

The anomaly engine will compare expected and detected locations and evaluate exit authorization.

**7. SQLite Database**

SQLite will store asset information, authorization records, and tracking events.

**8. Streamlit Dashboard**

Streamlit will provide a user interface for viewing asset statuses, event history, and security alerts.

### Current Architecture

The current software prototype uses simulated tracking events.

The ESP32, physical tracking hardware, MQTT integration, and dashboard are planned components and are not yet part of the working software prototype.

---

## 6. Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Programming language | Python | Application logic |
| Database | SQLite | Store assets and events |
| Data reporting | Pandas, if required by the selected report implementation | Tabular reports |
| IoT controller | ESP32 | Hardware integration |
| Tracking technology | RFID or BLE | Identify or detect assets |
| Wireless communication | Wi-Fi | Network connectivity |
| Messaging protocol | MQTT | Transfer tracking events |
| Dashboard | Streamlit | Visualize results |
| Development environment | VS Code | Code editing and execution |
| Version control | Git, optional | Track code changes |

### Tracking Technology Decision

The final tracking technology must be confirmed before hardware integration.

**RFID** is suitable for identifying assets at checkpoints and entry/exit points.

**BLE** can support proximity-based or zone-level indoor tracking through suitable gateways.

Neither technology automatically guarantees exact continuous location. Performance depends on hardware, placement, and the environment.

---

## 7. Asset and Location Model

The software prototype uses five sample assets.

| Asset ID | Asset Name | Expected Zone |
|---|---|---|
| A001 | Laptop | SHELF_01 |
| A002 | Monitor | SHELF_01 |
| A003 | Keyboard | SHELF_02 |
| A004 | Projector | SHELF_02 |
| A005 | Scanner | SHELF_03 |

### Defined Locations

- SHELF_01
- SHELF_02
- SHELF_03
- STORAGE
- MAIN_GATE
- NOT_DETECTED

These are example locations for development and testing. They can be changed to match a real warehouse or storage facility.

---

## 8. Asset Status Definitions

The project uses the following status categories.

### NORMAL

The asset was detected at its expected location.

### MISPLACED

The asset was detected in a location different from its expected location.

### MISSING

The asset has not been detected during the relevant checking process.

### MISSING_INVESTIGATION_REQUIRED

The asset is missing and requires further investigation. This status does not prove that the asset was stolen.

### AUTHORIZED_EXIT

The asset was detected at the main gate and has permission to leave.

### UNAUTHORIZED_EXIT

The asset was detected at the main gate without exit authorization.

### UNAUTHORIZED_REMOVAL

A software classification used when the asset is missing from its expected location, is detected at the gate, and lacks authorization. In a real deployment, the system must validate event timing and other evidence before treating this as a confirmed removal.

### UNKNOWN_ASSET

A tracking event refers to an asset ID that is not registered in the asset database.

---

## 9. Database Design

The system uses SQLite for local data storage.

The database file is named:

    asset_tracking.db

It is generated automatically when the database is initialized.

### Table 1: assets

Stores registered asset information.

| Column | Description |
|---|---|
| asset_id | Unique asset identifier |
| asset_name | Name of the asset |
| expected_zone | Assigned location |

### Table 2: events

Stores tracking and security events.

| Column | Description |
|---|---|
| event_id | Unique event number |
| asset_id | Identifier of the detected asset |
| event_type | Type of tracking event |
| location | Detected location |
| timestamp | Date and time of the event |
| status | Status assigned to the event |

### Table 3: authorization

Stores exit permissions.

| Column | Description |
|---|---|
| asset_id | Identifier of the asset |
| authorized_exit | 1 means authorized; 0 means unauthorized |

### Database Operations

The database code supports:

- Creating database tables.
- Inserting sample asset records.
- Inserting authorization records.
- Retrieving one asset or all assets.
- Checking exit authorization.
- Recording tracking events.
- Retrieving event history.
- Clearing previous events for a demonstration.

**Important:** The current demonstration clears previous event records when `main.py` runs. This behavior is intended for repeatable testing and should be changed before using the system for real monitoring.

---

## 10. Project Folder Structure

The current project files are kept in one folder.

    Phase1/
    |
    |-- main.py
    |-- config.py
    |-- database.py
    |-- anomaly_engine.py
    |-- setup_database.py
    |-- README.md
    |
    |-- asset_tracking.db

The exact files present in the folder may vary as development continues.

### File Descriptions

**main.py**

Runs the software prototype, processes simulated events, generates asset statuses, and displays reports.

**config.py**

Stores the database filename, location constants, and status names.

**database.py**

Creates and manages the SQLite database, including assets, events, and authorization records.

**anomaly_engine.py**

Contains functions that evaluate asset locations and determine final statuses.

**setup_database.py**

Initializes the database tables and inserts the sample assets and authorization records.

**README.md**

Documents the project, its architecture, implementation, setup instructions, and development plan.

**asset_tracking.db**

Stores the database records generated during execution.

The database file should be generated by the application rather than manually created.

---

## 11. Current Software Implementation

The software prototype simulates tracking events instead of receiving data from physical tracking hardware.

### Example Internal Events

    A001 -> SHELF_01
    A002 -> SHELF_03
    A004 -> SHELF_02

The software compares these detections against each asset's expected location.

### Example Gate Events

    A004 -> MAIN_GATE
    A005 -> MAIN_GATE

The software checks whether each asset is authorized to leave.

### Example Expected Report

    SMART ASSET TRACKING SYSTEM

    A001 | Laptop    | SHELF_01 | NORMAL
    A002 | Monitor   | SHELF_03 | MISPLACED
    A003 | Keyboard  | NOT_DETECTED | MISSING_INVESTIGATION_REQUIRED
    A004 | Projector | MAIN_GATE | AUTHORIZED_EXIT
    A005 | Scanner   | MAIN_GATE | UNAUTHORIZED_REMOVAL

The exact output depends on the simulated events and the implemented status rules.

The report is an example of the intended behavior, not a claim that physical IoT tracking is already operational.

---

## 12. Installation Requirements

### Software Requirements

- Python 3
- Visual Studio Code or another Python editor
- A terminal such as PowerShell or Command Prompt

SQLite is included with Python, so a separate database server is not required.

### Python Libraries

The current basic prototype uses Python's built-in `sqlite3` and `datetime` modules.

If the version of `main.py` being used imports Pandas, install it with:

    python -m pip install pandas

The core database and anomaly detection logic do not require Pandas.

For future phases, additional packages may be required for MQTT communication and the Streamlit dashboard.

---

## 13. How to Run the Current Prototype

### Step 1: Open the Project Folder

The current project folder is:

    C:\Users\NIGAM SHARMA\OneDrive\Desktop\Asset  Tracking system\Phase1

Open this folder in VS Code.

### Step 2: Open the Terminal

In VS Code, select Terminal → New Terminal.

### Step 3: Move to the Correct Directory

Run:

    cd "C:\Users\NIGAM SHARMA\OneDrive\Desktop\Asset  Tracking system\Phase1"

### Step 4: Initialize the Database

Run:

    python setup_database.py

This command creates the tables and inserts the sample assets and authorization records.

### Step 5: Run the Prototype

Run:

    python main.py

The software processes the simulated tracking events and displays the final report and security alerts.

### Important Execution Notes

- Run commands from the `Phase1` folder.
- Keep all required Python files in the same folder unless the import structure is deliberately changed.
- Check that filenames are correct, especially `anomaly_engine.py`.
- Initialize the database before running the prototype for the first time.
- If an error occurs, inspect the complete traceback and fix the underlying issue rather than creating duplicate files or databases.

---

## 14. Testing Plan for the Software Prototype

The following scenarios should be tested during Phase 2.

| Test | Input Scenario | Expected Result |
|---|---|---|
| 1 | Asset detected at expected zone | NORMAL |
| 2 | Asset detected at a different zone | MISPLACED |
| 3 | Asset not detected within the checking period | Missing investigation |
| 4 | Authorized asset detected at gate | AUTHORIZED_EXIT |
| 5 | Unauthorized asset detected at gate | UNAUTHORIZED_EXIT |
| 6 | Unregistered asset detected | UNKNOWN_ASSET |
| 7 | Missing asset detected at gate without permission | Potential UNAUTHORIZED_REMOVAL classification |

The implementation should be tested against each scenario before moving to IoT integration.

A separate automated test file can be added to verify the detection functions without requiring physical hardware.

---

## 15. Development Phases

The project is divided into six phases.

### Phase 1: System Design

Activities:

- Define the problem statement.
- Finalize the proposed solution.
- Design the architecture.
- Define asset and location models.
- Design the database.
- Identify the technology stack.

**Deliverable:** System design and project requirements.

### Phase 2: Software Prototype

Activities:

- Implement the database.
- Simulate asset tracking events.
- Implement location comparison.
- Implement exit authorization checks.
- Generate anomaly statuses.
- Store event history.
- Test the software logic.

**Deliverable:** A working Python software prototype with sample reports.

### Phase 3: IoT Communication

Activities:

- Configure ESP32 network connectivity.
- Set up an MQTT broker.
- Define the tracking-event message format.
- Connect the device to the messaging system.
- Verify communication between the device and backend.

**Deliverable:** A working IoT communication pipeline.

### Phase 4: Tracking Integration

Activities:

- Select and configure RFID or BLE hardware.
- Associate tracking identifiers with registered assets.
- Connect the selected tracking hardware to the ESP32 or suitable gateway.
- Send real or simulator-generated tracking events to the backend.

**Deliverable:** Tracking events integrated with the software system.

### Phase 5: Security and Anomaly Detection

Activities:

- Process real tracking events.
- Compare expected and detected locations.
- Apply missing-item checking rules.
- Validate exit authorization.
- Generate alerts for suspicious events.
- Test normal and abnormal movement scenarios.

**Deliverable:** Integrated asset security and anomaly detection.

### Phase 6: Dashboard and Final Testing

Activities:

- Build the Streamlit dashboard.
- Display asset locations and statuses.
- Display alerts and event history.
- Test the complete system.
- Record test results.
- Prepare documentation and the final demonstration.

**Deliverable:** Integrated IoT asset monitoring prototype with a dashboard, event history, and security alerts.

---

## 16. Current Limitations

The current software prototype has the following limitations:

1. Tracking events are simulated rather than obtained from physical sensors.
2. The system does not yet receive live MQTT messages.
3. The final RFID or BLE technology has not been confirmed.
4. Missing-item detection depends on the implemented checking process and configured time window.
5. Physical tag tampering is not detected without a suitable tamper sensor or mechanism.
6. A misplaced or missing asset cannot be assumed to be stolen without further evidence.
7. The Streamlit dashboard is planned but is not part of the current basic prototype.
8. Location accuracy will depend on tracking technology, reader placement, and the physical environment.

---

## 17. Future Enhancements

Possible improvements include:

- Real-time asset detection.
- RFID or BLE hardware integration.
- MQTT-based communication.
- Streamlit dashboard.
- Real-time security notifications.
- Configurable missing-item timeouts.
- Better event validation and duplicate-event handling.
- User roles and access control.
- Authorized movement history.
- Optional tag-tampering detection.
- Reports and exportable logs.
- Deployment testing in a small warehouse or laboratory environment.

---

## 18. Expected Final Outcome

The final system is intended to provide an IoT-based prototype that can:

- Identify registered assets.
- Monitor their detected zones.
- Flag misplaced assets.
- Flag missing assets for investigation.
- Verify authorized exits.
- Detect unauthorized exit events.
- Maintain tracking and security event history.
- Display results on a dashboard.
- Support further testing and future expansion.

The software prototype will first demonstrate the detection logic using simulated data. Later phases will integrate IoT communication and tracking hardware.

---

## 19. Conclusion

The IoT-Based Smart Asset Tracking and Unauthorized Movement Detection System aims to improve asset monitoring and security in warehouses, storage rooms, and similar environments.

The project follows a phased implementation strategy to make development manageable and testable.

Phase 1 established the proposed design. Phase 2 focuses on implementing and testing the Python software prototype. Subsequent phases will add IoT communication, tracking hardware, security integration, and dashboard functionality.

This approach allows the system's logic to be validated before investing time and resources in physical hardware integration.
