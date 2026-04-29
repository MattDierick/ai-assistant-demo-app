# Author : Matthieu DIERICK (For demo purpose only, not production ready code)

# A short section has been added into the code in order to send the prompt to F5 AI Guardrail (API integration)
# and check the response of the API Call. If the response is "cleared" prompt is sent to the LLM.
# Then the response from the LLM is also sent to F5 AI Guardrail and if the response is "cleared" it is sent back to the user.

# There are 2 more python files used for the settings part and the RAG part, 
# but the main logic is in this file. The settings.py file is used to manage the settings of the app and the rag_engine.py file is used to manage the RAG part of the app.

import os
import json
from flask import Flask, render_template, request, jsonify, session
import requests
from calypsoai import CalypsoAI
import rag_engine
from settings import settings_bp

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.register_blueprint(settings_bp)
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Pre-load rag.txt as the default RAG document
DEFAULT_RAG_FILE = os.path.join(os.path.dirname(__file__), "rag.txt")
_default_doc_id = rag_engine.load_default_document(DEFAULT_RAG_FILE)
if _default_doc_id:
    print(f"[INFO] Default RAG document 'rag.txt' loaded (id={_default_doc_id})")
else:
    print("[WARN] Default RAG document 'rag.txt' not found or already loaded.")


@app.route("/")
def index():
    return render_template("index.html")


# ────────────────────────────────────────────────────────────────────── 
# ── RAG Knowledge Base endpoints ──────────────────────────────────────
# ────────────────────────────────────────────────────────────────────── 

@app.route("/api/rag/upload", methods=["POST"])
def rag_upload():
    """Upload one or more TXT files into the RAG knowledge base."""
    if "files" not in request.files:
        return jsonify({"error": "No files provided."}), 400

    uploaded = []
    for f in request.files.getlist("files"):
        if not f.filename.lower().endswith(".txt"):
            continue
        text = f.read().decode("utf-8", errors="replace")
        doc_id = rag_engine.add_document(f.filename, text)
        # Also save file on disk so it survives quick inspection
        f.seek(0)
        f.save(os.path.join(UPLOAD_FOLDER, f"{doc_id}_{f.filename}"))
        uploaded.append({"id": doc_id, "name": f.filename})

    if not uploaded:
        return jsonify({"error": "No valid .txt files found in the upload."}), 400

    return jsonify({"uploaded": uploaded, "documents": rag_engine.list_documents()})


@app.route("/api/rag/documents", methods=["GET"])
def rag_list():
    """List documents currently loaded in the knowledge base."""
    return jsonify({"documents": rag_engine.list_documents()})


@app.route("/api/rag/documents/<doc_id>", methods=["DELETE"])
def rag_delete(doc_id):
    """Remove a document from the knowledge base."""
    if rag_engine.remove_document(doc_id):
        # Also remove from disk
        for fname in os.listdir(UPLOAD_FOLDER):
            if fname.startswith(doc_id):
                os.remove(os.path.join(UPLOAD_FOLDER, fname))
        return jsonify({"message": "Document removed.", "documents": rag_engine.list_documents()})
    return jsonify({"error": "Document not found."}), 404


@app.route("/api/rag/search", methods=["POST"])
def rag_search():
    """Test retrieval – returns matching chunks for a query."""
    data = request.get_json()
    query = (data or {}).get("query", "")
    if not query:
        return jsonify({"error": "No query provided."}), 400
    results = rag_engine.retrieve(query, top_k=5)
    return jsonify({"results": results})

# ────────────────────────────────────────────────────────────────────── 
# ── Chat endpoint ─────────────────────────────────────────────────────
# ────────────────────────────────────────────────────────────────────── 


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


    # ───────────────────────────────────────────────────────────────────────────────── 
    # ─── Scan the prompt with CalypsoAI before sending to the LLM (only if enabled) ──
    # ─── This is where I invoke the CalypsoAI SDK ────────────────────────────────────
    # ─────────────────────────────────────────────────────────────────────────────────

    calypso_enabled = settings.get("calypsoEnabled", False)
    cai = None

    if calypso_enabled:
        calypso_url = settings.get("calypsoUrl", "")
        calypso_token = settings.get("calypsoToken", "")
        if not calypso_url or not calypso_token:
            return jsonify({"error": "F5 AI Security is enabled but not configured. Add URL and token in Settings."}), 400

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

    # ─────────────────────────────────────────────────────────────────────────────
    # ── RAG: augment the messages with relevant context (if enabled) ─────────────
    # ─────────────────────────────────────────────────────────────────────────────

    rag_enabled = data.get("ragEnabled", False)
    augmented_messages = list(data["messages"])  # shallow copy

    if rag_enabled and user_prompt:
        rag_context = rag_engine.build_rag_context(user_prompt, top_k=3)
        if rag_context:
            # Insert a system message with the retrieved context
            augmented_messages.insert(0, {
                "role": "system",
                "content": rag_context,
            })
            print(f"[DEBUG] RAG context injected ({len(rag_context)} chars)")

    # ────────────────────────────────────────────────────────
    # ────── Send the prompt to the LLM endpoint ─────────────
    # ────────────────────────────────────────────────────────
    
    try:
        response = requests.post(
            settings["apiUrl"],
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings['apiKey']}",
            },
            json={
                "model": settings.get("modelName", "gpt-4o-mini"),
                "messages": augmented_messages,
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

        # ───────────────────────────────────────────────────────────────────────────────────────────────────
        # ───── Scan the LLM response with CalypsoAI before returning to the user (only if enabled) ─────────
        # ───────────────────────────────────────────────────────────────────────────────────────────────────

        if calypso_enabled and cai:
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
