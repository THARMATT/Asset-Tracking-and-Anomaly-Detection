# ==========================================
# FLASK REST API SERVER
# IoT-Based Smart Asset Tracking System
# ==========================================

import os
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS

from config import (
    DATABASE_PATH,
    FLASK_HOST,
    FLASK_PORT,
    FLASK_DEBUG,
    CORS_ORIGIN,
    INVALID_EVENT
)
from database import (
    initialize_database,
    get_connection,
    get_utc_now,
    get_asset,
    get_assets,
    update_asset,
    check_exit_authorization,
    set_exit_authorization,
    get_authorization,
    get_all_authorizations,
    get_exit_authorization_reason,
    get_events,
    retrieve_summary_counts,
    get_all_zones,
    get_audit_history
)
from anomaly_engine import (
    process_and_save_scan_event,
    run_and_save_inventory_audit
)
from mqtt_service import MQTTSubscriber
from location_service import (
    insert_location,
    get_latest_locations,
    get_asset_location_history,
    get_telemetry_history,
    VALID_SOURCES,
)
import iot_simulator.engine as iot_engine

# Configure readable logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("AssetTrackingAPI")


def create_app(test_config=None) -> Flask:
    """Application factory for the Flask REST API."""
    app = Flask(__name__)

    # Set stable database path in application configuration
    target_db = test_config.get("DATABASE_PATH") if test_config else DATABASE_PATH
    app.config["DATABASE_PATH"] = target_db

    # Restrict CORS to development frontend origins
    allowed_origins = [CORS_ORIGIN] if CORS_ORIGIN else ["http://localhost:5173", "http://127.0.0.1:5173"]
    if "http://localhost:5173" not in allowed_origins:
        allowed_origins.append("http://localhost:5173")
    if "http://127.0.0.1:5173" not in allowed_origins:
        allowed_origins.append("http://127.0.0.1:5173")

    CORS(app, resources={r"/api/*": {"origins": allowed_origins}})

    # Auto-initialize database on startup
    with app.app_context():
        initialize_database(db_path=target_db, seed=True)

    # Initialize MQTT subscriber service if enabled
    enable_mqtt = False
    if test_config is not None:
        enable_mqtt = test_config.get("ENABLE_MQTT", False)
    else:
        mqtt_env_flag = os.environ.get("ENABLE_MQTT", "true").lower() in ("true", "1", "yes")
        # In development mode, only connect from the reloader worker to prevent duplicate clients
        is_reloader_worker = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
        if mqtt_env_flag and (not app.debug or is_reloader_worker):
            enable_mqtt = True

    mqtt_sub = None
    if enable_mqtt:
        try:
            logger.info("Initializing integrated MQTT subscriber worker...")
            mqtt_sub = MQTTSubscriber(db_path=target_db)
            mqtt_sub.start()
        except Exception as exc:
            logger.error(f"Failed to start integrated MQTT subscriber: {exc}")
            mqtt_sub = None

    app.extensions["mqtt_subscriber"] = mqtt_sub

    # Auto-start the IoT simulator (unless we are in test mode)
    if test_config is None:
        try:
            is_reloader_worker = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
            # Only start in the reloader child process (or when not in debug mode)
            # to avoid launching two threads when Flask reloads.
            if not app.debug or is_reloader_worker:
                interval = float(os.environ.get("IOT_SIMULATOR_INTERVAL", "5"))
                iot_engine.start(db_path=target_db, interval_s=interval)
                logger.info("IoT simulator auto-started (interval=%.0fs).", interval)
        except Exception as exc:
            logger.error("Failed to auto-start IoT simulator: %s", exc)

    def get_db():
        """Retrieve the configured database path safely for current request context."""
        return app.config.get("DATABASE_PATH", DATABASE_PATH)

    # ==========================================
    # 1. SYSTEM & HEALTH CHECK
    # ==========================================
    @app.route("/api/health", methods=["GET"])
    def health_check():
        """
        Verify that the application is running and the database is accessible.
        Does not expose internal file paths or credentials.
        """
        try:
            with get_connection(get_db()) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1;")
                cursor.fetchone()

            sub = app.extensions.get("mqtt_subscriber")
            mqtt_status = "disabled"
            if sub:
                mqtt_status = "connected" if sub.is_connected else "disconnected"

            return jsonify({
                "status": "healthy",
                "service": "IoT Asset Tracking Backend",
                "database_status": "connected",
                "mqtt_status": mqtt_status,
                "timestamp": get_utc_now()
            }), 200

        except Exception as exc:
            logger.error(f"Health check database failure: {exc}")
            return jsonify({
                "status": "unhealthy",
                "service": "IoT Asset Tracking Backend",
                "database_status": "disconnected",
                "timestamp": get_utc_now()
            }), 503

    @app.route("/api/mqtt/status", methods=["GET"])
    def get_mqtt_diagnostics():
        """Retrieve live MQTT subscriber health, connection state, and operational metrics."""
        sub = app.extensions.get("mqtt_subscriber")
        if not sub:
            return jsonify({
                "success": True,
                "enabled": False,
                "status": "disabled",
                "message": "MQTT subscriber is not active on this instance"
            }), 200

        return jsonify({
            "success": True,
            "enabled": True,
            "connected": sub.is_connected,
            "status": "connected" if sub.is_connected else "disconnected",
            "host": sub.host,
            "port": sub.port,
            "topic": sub.topic,
            "queue_size": sub.event_queue.qsize(),
            "metrics": sub.metrics
        }), 200

    # ==========================================
    # 2. DASHBOARD SUMMARY
    # ==========================================
    @app.route("/api/summary", methods=["GET"])
    def get_summary():
        """
        Retrieve dashboard summary metrics with clear definitions.
        Includes registered assets, total events, normal, misplaced,
        authorized exits, unauthorized exits, unknown assets, and missing investigations.
        """
        try:
            summary = retrieve_summary_counts(db_path=get_db())
            return jsonify({
                "success": True,
                "data": summary
            }), 200
        except Exception as exc:
            logger.error(f"Failed to fetch summary: {exc}")
            return jsonify({
                "success": False,
                "error": "Failed to retrieve summary metrics"
            }), 500

    # ==========================================
    # 3. ASSET MANAGEMENT ENDPOINTS
    # ==========================================
    @app.route("/api/assets", methods=["GET"])
    def list_assets():
        """
        Return registered physical assets.
        Supports optional '?active_only=true' filter.
        """
        active_only = request.args.get("active_only", "false").lower() in ("true", "1")
        assets = get_assets(active_only=active_only, db_path=get_db())
        return jsonify({
            "success": True,
            "count": len(assets),
            "data": assets
        }), 200

    @app.route("/api/assets/<asset_id>", methods=["GET"])
    def retrieve_single_asset(asset_id: str):
        """Return details of a single registered asset or 404."""
        clean_id = str(asset_id).strip()
        asset = get_asset(clean_id, db_path=get_db())
        if not asset:
            return jsonify({
                "success": False,
                "error": f"Asset '{clean_id}' not found"
            }), 404

        return jsonify({
            "success": True,
            "data": asset
        }), 200

    @app.route("/api/assets/<asset_id>", methods=["PUT"])
    def modify_asset(asset_id: str):
        """Safely update asset metadata or exit authorization."""
        clean_id = str(asset_id).strip()
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({
                "success": False,
                "error": "Request body must be a valid JSON object"
            }), 400

        updated = update_asset(
            asset_id=clean_id,
            asset_name=payload.get("asset_name"),
            category=payload.get("category"),
            expected_zone=payload.get("expected_zone"),
            active=payload.get("active"),
            authorized_exit=payload.get("authorized_exit"),
            notes=payload.get("notes"),
            db_path=get_db()
        )

        if not updated:
            return jsonify({
                "success": False,
                "error": f"Asset '{clean_id}' not found"
            }), 404

        return jsonify({
            "success": True,
            "message": f"Asset '{clean_id}' updated successfully",
            "data": updated
        }), 200

    # ==========================================
    # 4. TRACKING EVENT ENDPOINTS
    # ==========================================
    @app.route("/api/events", methods=["GET"])
    def list_events():
        """
        Return tracking event history with safe pagination and filters.
        Query params:
        - limit: int (default 50, max 200)
        - offset: int (default 0)
        - asset_id: str (filter by asset)
        - status: str (filter by status e.g. MISPLACED, UNAUTHORIZED_EXIT)
        - zone / location: str (filter by zone)
        """
        try:
            limit = request.args.get("limit", 50, type=int)
            offset = request.args.get("offset", 0, type=int)
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid pagination parameters"}), 400

        asset_id = request.args.get("asset_id")
        status = request.args.get("status")
        location = request.args.get("zone") or request.args.get("location")

        results = get_events(
            limit=limit,
            offset=offset,
            asset_id=asset_id.strip() if asset_id else None,
            status=status.strip() if status else None,
            location=location.strip() if location else None,
            db_path=get_db()
        )
        return jsonify({
            "success": True,
            "data": results
        }), 200

    @app.route("/api/events", methods=["POST"])
    def ingest_tracking_event():
        """
        Ingest a simulated or external asset scan event.
        - Validates JSON format, required fields, and zone recognition.
        - Routes payload through the shared anomaly detection engine.
        - Client-supplied status is NEVER allowed to override backend classification.
        - Prevents duplicate insertion when an existing message_id is re-sent.
        """
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({
                "success": False,
                "error": "Request body must be a valid JSON dictionary",
                "status": INVALID_EVENT
            }), 400

        # Send through the shared anomaly engine processing service
        processed = process_and_save_scan_event(payload, db_path=get_db())

        # If payload was malformed or zone was unrecognized
        if processed["status"] == INVALID_EVENT:
            return jsonify({
                "success": False,
                "error": processed["message"],
                "status": INVALID_EVENT,
                "data": processed
            }), 400

        persistence_info = processed.get("persistence", {})
        is_duplicate = persistence_info.get("duplicate", False)

        if is_duplicate:
            return jsonify({
                "success": True,
                "message": "Event already processed (deduplicated)",
                "duplicate": True,
                "data": processed
            }), 200

        return jsonify({
            "success": True,
            "message": "Event processed and recorded successfully",
            "duplicate": False,
            "data": processed
        }), 201

    # ==========================================
    # 5. INVENTORY AUDIT ENDPOINTS
    # ==========================================
    @app.route("/api/audits", methods=["GET"])
    def list_audits():
        """Return inventory audit execution history with pagination."""
        try:
            limit = request.args.get("limit", 50, type=int)
            offset = request.args.get("offset", 0, type=int)
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid pagination parameters"}), 400

        audits = get_audit_history(limit=limit, offset=offset, db_path=get_db())
        return jsonify({
            "success": True,
            "data": audits
        }), 200

    @app.route("/api/audits", methods=["POST"])
    def execute_audit():
        """
        Trigger a formal inventory audit against a list of scanned asset IDs.
        Flags undetected expected assets for investigation.
        """
        payload = request.get_json(silent=True) or {}
        scanned_asset_ids = payload.get("scanned_asset_ids")

        if not isinstance(scanned_asset_ids, list):
            return jsonify({
                "success": False,
                "error": "'scanned_asset_ids' must be an array of asset IDs"
            }), 400

        notes = payload.get("notes")
        audit_report = run_and_save_inventory_audit(
            scanned_asset_ids=scanned_asset_ids,
            notes=notes,
            db_path=get_db()
        )

        return jsonify({
            "success": True,
            "message": "Inventory audit completed successfully",
            "data": audit_report
        }), 201

    # ==========================================
    # 6. FACILITY ZONES & AUTHORIZATION
    # ==========================================
    @app.route("/api/zones", methods=["GET"])
    def list_zones():
        """List predefined and registered facility zones."""
        zones = get_all_zones(db_path=get_db())
        return jsonify({
            "success": True,
            "count": len(zones),
            "data": zones
        }), 200

    @app.route("/api/authorization", methods=["GET"])
    def list_authorizations():
        """List all authorization records with asset details."""
        records = get_all_authorizations(db_path=get_db())
        return jsonify({
            "success": True,
            "count": len(records),
            "data": records
        }), 200

    @app.route("/api/authorization/<asset_id>", methods=["GET"])
    def get_authorization_status(asset_id: str):
        """Check exit authorization for an asset, returning the full record."""
        clean_id = str(asset_id).strip()
        record = get_authorization(clean_id, db_path=get_db())
        if record is None:
            return jsonify({
                "success": True,
                "asset_id": clean_id,
                "authorized_exit": False,
                "record": None
            }), 200
        return jsonify({
            "success": True,
            "asset_id": clean_id,
            "authorized_exit": bool(check_exit_authorization(clean_id, db_path=get_db())),
            "record": record
        }), 200

    @app.route("/api/authorization/<asset_id>", methods=["PUT"])
    def set_authorization_status(asset_id: str):
        """Set or toggle exit authorization flag for an asset."""
        clean_id = str(asset_id).strip()
        payload = request.get_json(silent=True) or {}
        if "authorized_exit" not in payload:
            return jsonify({
                "success": False,
                "error": "'authorized_exit' field (0 or 1) is required"
            }), 400

        # Validate ISO 8601 date fields if provided
        for date_field in ("valid_until", "revoked_at"):
            val = payload.get(date_field)
            if val is not None:
                try:
                    from datetime import datetime as _dt
                    _dt.fromisoformat(str(val).replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    return jsonify({
                        "success": False,
                        "error": f"'{date_field}' must be a valid ISO 8601 timestamp"
                    }), 400

        success = set_exit_authorization(
            asset_id=clean_id,
            authorized_exit=int(payload["authorized_exit"]),
            notes=payload.get("notes"),
            valid_until=payload.get("valid_until"),
            requested_by=payload.get("requested_by"),
            approved_by=payload.get("approved_by"),
            revoked_at=payload.get("revoked_at"),
            revocation_reason=payload.get("revocation_reason"),
            db_path=get_db()
        )
        if not success:
            return jsonify({
                "success": False,
                "error": f"Asset '{clean_id}' does not exist"
            }), 404

        updated_record = get_authorization(clean_id, db_path=get_db())
        return jsonify({
            "success": True,
            "message": f"Exit authorization for '{clean_id}' updated",
            "security_notice": "PROTOTYPE: Authorization changes take effect immediately at gate.",
            "authorized_exit": bool(payload["authorized_exit"]),
            "record": updated_record
        }), 200

    # ==========================================
    # 7. SPATIAL LOCATION ENDPOINTS
    # ==========================================
    # DESIGN CONSTRAINT: These endpoints manage GPS/spatial coordinates only.
    # Location data NEVER influences anomaly status, gate authorization, or exit
    # permissions. Those are controlled exclusively by RFID scan events and the
    # authorization table. Coordinates from 'simulator'/'manual' sources are
    # explicitly labeled as approximate and must not be mistaken for real sensor data.

    @app.route("/api/locations/latest", methods=["GET"])
    def list_latest_locations():
        """
        Return the most recent location record for every asset that has one.
        Includes asset metadata and source label so the UI can display
        SIMULATED vs DEVICE badges.
        """
        try:
            locations = get_latest_locations(db_path=get_db())
            return jsonify({
                "success": True,
                "count": len(locations),
                "data": locations,
                "notice": "Coordinates labeled 'simulator' or 'manual' are approximate and not real GPS fixes."
            }), 200
        except Exception as exc:
            logger.error(f"Failed to fetch latest locations: {exc}")
            return jsonify({"success": False, "error": "Failed to retrieve latest locations"}), 500

    @app.route("/api/assets/<asset_id>/locations", methods=["GET"])
    def get_location_history(asset_id: str):
        """
        Return the N most recent location records for a single asset.
        Query params:
        - limit: int (default 100, max 500)
        """
        clean_id = str(asset_id).strip()
        # Verify asset exists first
        asset = get_asset(clean_id, db_path=get_db())
        if asset is None:
            return jsonify({"success": False, "error": f"Asset '{clean_id}' not found"}), 404

        try:
            limit = request.args.get("limit", 100, type=int)
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid 'limit' parameter"}), 400

        try:
            history = get_asset_location_history(clean_id, limit=limit, db_path=get_db())
            return jsonify({
                "success": True,
                "asset_id": clean_id,
                "count": len(history),
                "data": history
            }), 200
        except Exception as exc:
            logger.error(f"Failed to fetch location history for asset '{clean_id}': {exc}")
            return jsonify({"success": False, "error": "Failed to retrieve location history"}), 500

    @app.route("/api/locations", methods=["POST"])
    def record_location():
        """
        Record a new asset location.
        Required fields: asset_id, latitude, longitude
        Optional fields: source (default 'simulator'), accuracy_m, message_id,
                         temperature, battery_level, speed, recorded_at

        Latitude:  -90  to  90
        Longitude: -180 to 180
        Source:    one of 'device', 'simulator', 'manual'

        IMPORTANT: Submitting a location NEVER modifies gate authorization or
        anomaly classification. Those are exclusively controlled by RFID events.
        """
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"success": False, "error": "Request body must be a valid JSON object"}), 400

        # Required fields
        missing = [f for f in ("asset_id", "latitude", "longitude") if f not in payload]
        if missing:
            return jsonify({
                "success": False,
                "error": f"Missing required fields: {', '.join(missing)}"
            }), 400

        try:
            result = insert_location(
                asset_id=str(payload["asset_id"]).strip(),
                latitude=payload["latitude"],
                longitude=payload["longitude"],
                source=payload.get("source", "simulator"),
                accuracy_m=payload.get("accuracy_m"),
                message_id=payload.get("message_id"),
                temperature=payload.get("temperature"),
                battery_level=payload.get("battery_level"),
                speed=payload.get("speed"),
                recorded_at=payload.get("recorded_at"),
                db_path=get_db()
            )
        except LookupError as e:
            return jsonify({"success": False, "error": str(e)}), 404
        except ValueError as e:
            return jsonify({"success": False, "error": str(e)}), 400
        except Exception as exc:
            logger.error(f"Failed to record location: {exc}")
            return jsonify({"success": False, "error": "Failed to record location"}), 500

        if result.get("duplicate"):
            return jsonify({
                "success": True,
                "duplicate": True,
                "message": result["message"],
                "data": result
            }), 200

        return jsonify({
            "success": True,
            "duplicate": False,
            "message": result["message"],
            "data": result
        }), 201

    @app.route("/api/telemetry/history", methods=["GET"])
    def list_telemetry_history():
        """
        Return location rows containing at least one non-null telemetry field
        (temperature, battery_level, speed).
        Query params:
        - asset_id: str (optional filter)
        - limit: int (default 50, max 500)
        """
        try:
            limit = request.args.get("limit", 50, type=int)
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid 'limit' parameter"}), 400

        asset_id = request.args.get("asset_id")
        try:
            rows = get_telemetry_history(
                asset_id=asset_id.strip() if asset_id else None,
                limit=limit,
                db_path=get_db()
            )
            return jsonify({
                "success": True,
                "count": len(rows),
                "data": rows
            }), 200
        except Exception as exc:
            logger.error(f"Failed to fetch telemetry history: {exc}")
            return jsonify({"success": False, "error": "Failed to retrieve telemetry history"}), 500

    @app.route("/api/simulator/movement", methods=["POST"])
    def simulate_movement():
        """
        Simulate a batch of location updates for demo purposes.
        Only active when LOCATION_SIMULATOR_ENABLED=True environment variable is set.
        Each call records one new simulated location per asset_id provided.

        Returns 403 if the simulator feature is not enabled.

        REMINDER: Simulated locations are labeled source='simulator' and are
        explicitly approximate. They do not affect RFID/gate/anomaly logic.
        """
        enabled = os.environ.get("LOCATION_SIMULATOR_ENABLED", "false").lower() in ("true", "1", "yes")
        if not enabled:
            return jsonify({
                "success": False,
                "error": "Location simulator is disabled. Set LOCATION_SIMULATOR_ENABLED=True to enable.",
                "enabled": False
            }), 403

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"success": False, "error": "Request body must be a valid JSON object"}), 400

        # Required
        missing = [f for f in ("asset_id", "latitude", "longitude") if f not in payload]
        if missing:
            return jsonify({
                "success": False,
                "error": f"Missing required fields: {', '.join(missing)}"
            }), 400

        try:
            result = insert_location(
                asset_id=str(payload["asset_id"]).strip(),
                latitude=payload["latitude"],
                longitude=payload["longitude"],
                source="simulator",
                accuracy_m=payload.get("accuracy_m"),
                message_id=payload.get("message_id"),
                temperature=payload.get("temperature"),
                battery_level=payload.get("battery_level"),
                speed=payload.get("speed"),
                recorded_at=payload.get("recorded_at"),
                db_path=get_db()
            )
        except LookupError as e:
            return jsonify({"success": False, "error": str(e)}), 404
        except ValueError as e:
            return jsonify({"success": False, "error": str(e)}), 400
        except Exception as exc:
            logger.error(f"Simulator movement failed: {exc}")
            return jsonify({"success": False, "error": "Failed to simulate movement"}), 500

        return jsonify({
            "success": True,
            "simulated": True,
            "notice": "This is a simulated location (source=simulator). Not a real GPS fix.",
            "data": result
        }), 201

    # ==========================================
    # 8. ERROR HANDLERS (SAFE, NO LEAKED TRACES)
    # ==========================================
    @app.errorhandler(400)
    def handle_bad_request(e):
        desc = getattr(e, "description", "Bad request syntax or invalid parameters")
        return jsonify({"success": False, "error": str(desc)}), 400

    @app.errorhandler(404)
    def handle_not_found(e):
        return jsonify({"success": False, "error": "Resource not found"}), 404

    @app.errorhandler(500)
    def handle_internal_error(e):
        logger.error(f"Internal server error: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "An internal server error occurred. Please contact system administrator."
        }), 500

    # ==========================================
    # 8. IoT SIMULATOR ROUTES
    # ==========================================

    @app.route("/api/iot/status", methods=["GET"])
    def iot_status():
        """Return current IoT simulator engine status."""
        return jsonify({"success": True, "data": iot_engine.get_status()}), 200

    @app.route("/api/iot/start", methods=["POST"])
    def iot_start():
        """Start the IoT simulator background engine."""
        interval = float(request.json.get("interval_s", 5.0)) if request.is_json else 5.0
        interval = max(2.0, min(interval, 60.0))
        try:
            iot_engine.start(db_path=target_db, interval_s=interval)
            return jsonify({"success": True, "message": "IoT simulator started.",
                            "data": iot_engine.get_status()}), 200
        except Exception as exc:
            logger.error("Failed to start IoT simulator: %s", exc)
            return jsonify({"success": False, "error": str(exc)}), 500

    @app.route("/api/iot/stop", methods=["POST"])
    def iot_stop():
        """Stop the IoT simulator background engine."""
        iot_engine.stop()
        return jsonify({"success": True, "message": "IoT simulator stopped.",
                        "data": iot_engine.get_status()}), 200

    @app.route("/api/iot/pause", methods=["POST"])
    def iot_pause():
        """Pause the IoT simulator (keep thread alive but stop ticking)."""
        iot_engine.pause()
        return jsonify({"success": True, "message": "IoT simulator paused.",
                        "data": iot_engine.get_status()}), 200

    @app.route("/api/iot/resume", methods=["POST"])
    def iot_resume():
        """Resume a paused IoT simulator."""
        iot_engine.resume()
        return jsonify({"success": True, "message": "IoT simulator resumed.",
                        "data": iot_engine.get_status()}), 200

    @app.route("/api/iot/tick", methods=["POST"])
    def iot_tick():
        """Manually trigger one simulation cycle."""
        demo = (request.json or {}).get("demo_anomaly", False) if request.is_json else False
        try:
            status = iot_engine.trigger_tick(force_demo_anomaly=bool(demo))
            return jsonify({"success": True, "message": "Tick complete.", "data": status}), 200
        except RuntimeError as exc:
            return jsonify({"success": False,
                            "error": str(exc) + " Start the simulator first."}), 400

    @app.route("/api/iot/readings", methods=["GET"])
    def iot_readings():
        """Return latest in-memory reading for every IoT asset."""
        return jsonify({"success": True, "data": iot_engine.get_latest_readings()}), 200

    return app


app = create_app()

if __name__ == "__main__":
    logger.info(f"Starting Asset Tracking REST API on {FLASK_HOST}:{FLASK_PORT} (Debug={FLASK_DEBUG})")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
