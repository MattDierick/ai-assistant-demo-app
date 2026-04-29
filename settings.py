# This file contains the backend logic for managing user settings in the AI Assistant Demo App.
# Many controls have been added in the code to be sure the file imported is correct.

import json
from flask import Blueprint, request, jsonify, session, current_app

settings_bp = Blueprint("settings", __name__)

# ────────────────────────────────────────────────────────────────────────
# ── Default settings template ──────────────────────────────────────────
# ────────────────────────────────────────────────────────────────────────

DEFAULT_SETTINGS = {
    "apiUrl": "",
    "apiKey": "",
    "modelName": "gpt-4o-mini",
    "calypsoEnabled": False,
    "calypsoUrl": "https://www.us2.calypsoai.app",
    "calypsoToken": "",
}


# ────────────────────────────────────────────────────────────────────────
# ── GET / POST settings ────────────────────────────────────────────────
# ────────────────────────────────────────────────────────────────────────

@settings_bp.route("/api/settings", methods=["GET"])
def get_settings():
    settings = session.get("settings", DEFAULT_SETTINGS.copy())
    # Never send secrets back to the client
    safe_settings = {
        "apiUrl": settings.get("apiUrl", ""),
        "apiKey": "••••••••" if settings.get("apiKey") else "",
        "modelName": settings.get("modelName", "gpt-4o-mini"),
        "calypsoEnabled": settings.get("calypsoEnabled", False),
        "calypsoUrl": settings.get("calypsoUrl", ""),
        "calypsoToken": "••••••••" if settings.get("calypsoToken") else "",
    }
    return jsonify(safe_settings)


@settings_bp.route("/api/settings", methods=["POST"])
def save_settings():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    # Preserve existing secrets if not provided in the update
    existing = session.get("settings", {})
    session["settings"] = {
        "apiUrl": data.get("apiUrl", "").strip(),
        "apiKey": data.get("apiKey", "").strip() or existing.get("apiKey", ""),
        "modelName": data.get("modelName", "gpt-4o-mini").strip(),
        "calypsoEnabled": bool(data.get("calypsoEnabled", False)),
        "calypsoUrl": data.get("calypsoUrl", "").strip() or existing.get("calypsoUrl", "https://www.us2.calypsoai.app"),
        "calypsoToken": data.get("calypsoToken", "").strip() or existing.get("calypsoToken", ""),
    }
    return jsonify({"message": "Settings saved on the server."})


# ────────────────────────────────────────────────────────────────────────
# ── Export settings ────────────────────────────────────────────────────
# ────────────────────────────────────────────────────────────────────────

@settings_bp.route("/api/settings/export", methods=["GET"])
def export_settings():
    """Export the current configuration as a downloadable JSON file with real secrets."""
    settings = session.get("settings", {})
    export_data = {
        "llm": {
            "apiUrl": settings.get("apiUrl", ""),
            "apiKey": settings.get("apiKey", ""),
            "modelName": settings.get("modelName", "gpt-4o-mini"),
        },
        "f5_ai_security": {
            "enabled": settings.get("calypsoEnabled", False),
            "url": settings.get("calypsoUrl", ""),
            "token": settings.get("calypsoToken", ""),
        },
    }
    resp = current_app.response_class(
        response=json.dumps(export_data, indent=2),
        status=200,
        mimetype="application/json",
        headers={
            "Content-Disposition": "attachment; filename=ai-assistant-config.json"
        },
    )
    return resp


# ────────────────────────────────────────────────────────────────────────
# ── Import settings ────────────────────────────────────────────────────
# ────────────────────────────────────────────────────────────────────────

@settings_bp.route("/api/settings/import", methods=["POST"])
def import_settings():
    """Import configuration from a previously exported JSON file."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided."}), 400

    f = request.files["file"]
    if not f.filename.lower().endswith(".json"):
        return jsonify({"error": "Only .json files are accepted."}), 400

    try:
        data = json.loads(f.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return jsonify({"error": "Invalid JSON file."}), 400

    llm = data.get("llm", {})
    f5 = data.get("f5_ai_security", {})

    # Merge imported values with existing settings, keeping secrets that
    # are masked (bullet characters) or empty unchanged.
    existing = session.get("settings", {})
    mask = "\u2022" * 8

    new_api_key = llm.get("apiKey", "")
    if not new_api_key or new_api_key == mask:
        new_api_key = existing.get("apiKey", "")

    new_token = f5.get("token", "")
    if not new_token or new_token == mask:
        new_token = existing.get("calypsoToken", "")

    session["settings"] = {
        "apiUrl": llm.get("apiUrl", "").strip() or existing.get("apiUrl", ""),
        "apiKey": new_api_key,
        "modelName": llm.get("modelName", "").strip() or existing.get("modelName", "gpt-4o-mini"),
        "calypsoEnabled": bool(f5.get("enabled", existing.get("calypsoEnabled", False))),
        "calypsoUrl": f5.get("url", "").strip() or existing.get("calypsoUrl", "https://www.us2.calypsoai.app"),
        "calypsoToken": new_token,
    }

    return jsonify({
        "message": "Configuration imported successfully.",
        "hasApiKey": bool(new_api_key),
        "hasToken": bool(new_token),
    })