import os, json
from flask import Flask, render_template, request, session, redirect, jsonify
from dotenv import load_dotenv

from services.notion_service import NotionService
from services.ai_service import AIService
from prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from utils import chunk_text, merge_payloads

load_dotenv()  # loads .env

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "dev-secret")

notion = NotionService()
ai = AIService()

@app.route("/", methods=["GET"])
def index():
    notes = notion.fetch_all_notes_text()
    preview = (notes[:1200] + "…") if notes and len(notes) > 1200 else notes
    generated = session.get("generated")
    return render_template("index.html", preview_notes=preview, generated=generated)

@app.route("/generate", methods=["POST"])
def generate():
    difficulty = request.form.get("difficulty", "balanced")
    focus = request.form.get("focus", "").strip() or "none"
    notes = notion.fetch_all_notes_text()
    if not notes:
        return render_template("index.html", preview_notes="", generated=None, subtitle="No notes found in Notion.")

    chunks = chunk_text(notes, max_chars=7000, overlap=400)
    payloads = []
    for ch in chunks:
        up = USER_PROMPT_TEMPLATE.format(notes=ch, difficulty=difficulty, focus=focus)
        payloads.append(ai.generate_exam_json(SYSTEM_PROMPT, up))
    merged = merge_payloads(payloads)

    session["generated"] = merged
    return render_template("index.html",
                           preview_notes=(notes[:1200]+"…") if len(notes) > 1200 else notes,
                           generated=merged)

# ----- MCQ Quiz -----
@app.route("/quiz/mcq", methods=["GET", "POST"])
def quiz_mcq():
    data = session.get("generated")
    if not data: return redirect("/")
    mcqs = data.get("mcqs", [])

    if request.method == "GET":
        return render_template("quiz_mcq.html", mcqs=mcqs, enumerate=enumerate)

    # POST: grade
    score = 0; review = []
    for i, q in enumerate(mcqs):
        correct_idx = int(q.get("answer_index", -1))
        your_idx_raw = request.form.get(f"q{i}")
        try:
            your_idx = int(your_idx_raw)
        except (TypeError, ValueError):
            your_idx = -1
        if your_idx == correct_idx:
            score += 1
        review.append({
            "q": q["q"],
            "your_answer_text": q["choices"][your_idx] if 0 <= your_idx < len(q["choices"]) else "(no answer)",
            "correct_answer_text": q["choices"][correct_idx] if 0 <= correct_idx < len(q["choices"]) else "(n/a)",
            "explanation": q.get("explanation", "")
        })
    return render_template("results.html", score=score, total=len(mcqs), review=review)

# ----- Flashcards -----
@app.route("/quiz/flashcards", methods=["GET"])
def quiz_flashcards():
    data = session.get("generated")
    if not data: return redirect("/")
    flashcards = data.get("flashcards", [])
    return render_template("quiz_flashcards.html", flashcards=flashcards, enumerate=enumerate)

@app.route("/api/flashcards/save", methods=["POST"])
def save_flashcard():
    """Save a flashcard to the user's permanent collection"""
    data = request.get_json()
    if not data or 'question' not in data or 'answer' not in data:
        return jsonify({"error": "Invalid flashcard data"}), 400
    
    # Get existing saved flashcards from session
    saved_flashcards = session.get("saved_flashcards", [])
    
    # Add new flashcard with timestamp
    new_card = {
        "id": len(saved_flashcards) + 1,
        "question": data["question"],
        "answer": data["answer"],
        "saved_at": data.get("saved_at")
    }
    
    saved_flashcards.append(new_card)
    session["saved_flashcards"] = saved_flashcards
    
    return jsonify({"success": True, "message": "Flashcard saved successfully"})

@app.route("/api/flashcards/saved", methods=["GET"])
def get_saved_flashcards():
    """Retrieve all saved flashcards"""
    saved_flashcards = session.get("saved_flashcards", [])
    return jsonify({"flashcards": saved_flashcards})

# ----- Mock exam viewer -----
@app.route("/mock-exam", methods=["GET"])
def mock_exam():
    data = session.get("generated")
    if not data: return redirect("/")
    mock = data.get("mock_exam", {"title":"Mock Exam","questions":[]})
    return render_template("mock_exam.html", mock=mock)

# Optional quick debug endpoint
@app.route("/debug/notion")
def debug_notion():
    text = notion.fetch_all_notes_text()
    return f"<pre>{(text[:10000] + '…') if text and len(text)>10000 else text}</pre>"

if __name__ == "__main__":
    app.run(debug=True)
