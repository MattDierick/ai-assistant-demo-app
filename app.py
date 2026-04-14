# A short section has been added into the code in order to send the prompt to F5 AI Guardrail (API integration)
# and check the response of the API Call. If the response is "cleared" prompt is sent to the LLM.
# Then the response from the LLM is also sent to F5 AI Guardrail and if the response is "cleared" it is sent back to the user.


import os
import json
from flask import Flask, render_template, request, jsonify, session
import requests
from calypsoai import CalypsoAI

app = Flask(__name__)
app.secret_key = os.urandom(24)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/settings", methods=["GET"])
def get_settings():
    settings = session.get("settings", {
        "apiUrl": "",
        "apiKey": "",
        "modelName": "gpt-4o-mini",
        "calypsoUrl": "https://www.us2.calypsoai.app",
        "calypsoToken": "",
    })
    # Never send secrets back to the client
    safe_settings = {
        "apiUrl": settings.get("apiUrl", ""),
        "apiKey": "••••••••" if settings.get("apiKey") else "",
        "modelName": settings.get("modelName", "gpt-4o-mini"),
        "calypsoUrl": settings.get("calypsoUrl", ""),
        "calypsoToken": "••••••••" if settings.get("calypsoToken") else "",
    }
    return jsonify(safe_settings)


@app.route("/api/settings", methods=["POST"])
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
        "calypsoUrl": data.get("calypsoUrl", "").strip() or existing.get("calypsoUrl", "https://www.us2.calypsoai.app"),
        "calypsoToken": data.get("calypsoToken", "").strip() or existing.get("calypsoToken", ""),
    }
    return jsonify({"message": "Settings saved on the server."})


@app.route("/api/chat", methods=["POST"])
def chat():
    settings = session.get("settings")
    if not settings or not settings.get("apiUrl") or not settings.get("apiKey"):
        return jsonify({"error": "API not configured. Save your settings first."}), 400

    data = request.get_json()
    if not data or "messages" not in data:
        return jsonify({"error": "No messages provided."}), 400

    # Extract the latest user message
    user_prompt = ""
    for msg in reversed(data["messages"]):
        if msg.get("role") == "user":
            user_prompt = msg.get("content", "")
            break

    # Scan the prompt with CalypsoAI before sending to the LLM
    calypso_url = settings.get("calypsoUrl", "")
    calypso_token = settings.get("calypsoToken", "")
    if not calypso_url or not calypso_token:
        return jsonify({"error": "F5 AI Security not configured. Add URL and token in Settings."}), 400

    try:
        cai = CalypsoAI(url=calypso_url, token=calypso_token)
        scan_result = cai.scans.scan(user_prompt)
        scan_data = json.loads(scan_result.model_dump_json())
        outcome = scan_data.get("result", {}).get("outcome", "")
        print(f"[DEBUG] prompt outcome: {outcome}")
        if outcome != "cleared":
            return jsonify({"content": "Blocked by F5 AI Security"})
    except Exception as e:
        return jsonify({"error": f"F5 AI Security scan failed: {str(e)}"}), 502

    # Send the prompt to the LLM endpoint if cleared by CalypsoAI
    try:
        response = requests.post(
            settings["apiUrl"],
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings['apiKey']}",
            },
            json={
                "model": settings.get("modelName", "gpt-4o-mini"),
                "messages": data["messages"],
            },
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()

        first_choice = result.get("choices", [{}])[0]
        content = first_choice.get("message", {}).get("content", "")

        if isinstance(content, list):
            content = "".join(item.get("text", "") for item in content).strip()

        if not content:
            return jsonify({"error": "The API response did not contain assistant text."}), 502

        # Scan the LLM response with CalypsoAI before returning to the user
        try:
            response_scan_result = cai.scans.scan(content.strip())
            response_scan_data = json.loads(response_scan_result.model_dump_json())
            response_outcome = response_scan_data.get("result", {}).get("outcome", "")
            print(f"[DEBUG] response outcome: {response_outcome}")
            if response_outcome != "cleared":
                return jsonify({"content": "Response blocked by F5 AI Security"})
        except Exception as e:
            return jsonify({"error": f"F5 AI Security response scan failed: {str(e)}"}), 502

        return jsonify({"content": content.strip()})

    except requests.exceptions.Timeout:
        return jsonify({"error": "Request to the API timed out."}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Could not connect to the API endpoint."}), 502
    except requests.exceptions.HTTPError as e:
        return jsonify({"error": f"{e.response.status_code} {e.response.reason} - {e.response.text}"}), e.response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8800)
