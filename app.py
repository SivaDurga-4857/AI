from flask import Flask, render_template, request, redirect
import sqlite3
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json

app = Flask(__name__)

# Load environment variables
load_dotenv()
print("API KEY =", os.getenv("GEMINI_API_KEY"))

# Gemini API Setup
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Gemini Model
model = genai.GenerativeModel("gemini-2.5-flash")

# Create Database and Table
def init_db():
    conn = sqlite3.connect("planner.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task TEXT,
    status TEXT,
    difficulty TEXT,
    study_hours INTEGER,
    reason TEXT,
    score INTEGER,
    level TEXT
)
""") 

    conn.commit()
    conn.close()

init_db()


# Get Task Priority using Gemini


def get_priority(task):

    task_lower = task.lower()

    if task_lower in ["dsa", "data structures", "algorithms"]:
        return {
            "difficulty": "High",
            "study_hours": 4,
            "reason": "Most important placement topic"
        }

    if task_lower in [
        "dbms",
        "os",
        "operating system",
        "oops",
        "computer networks",
        "cn"
    ]:
        return {
            "difficulty": "High",
            "study_hours": 3,
            "reason": "Core CS placement subject"
        }

    prompt = f"""
    Classify this Computer Science topic.

    Return JSON only:

    {{
        "difficulty":"High",
        "study_hours":2,
        "reason":"short reason"
    }}

    Topic: {task}
    """

    try:
        response = model.generate_content(prompt)

        data = json.loads(response.text)

        return data

    except Exception as e:

        print("Gemini Error:", e)

        return {
            "difficulty": "Easy",
            "study_hours": 1,
            "reason": "Default value"
        }

def generate_quiz(topic):

    prompt = f"""
Generate exactly 5 multiple choice questions about {topic}.

Return ONLY valid JSON in this format:

{{
    "questions": [
        {{
            "question": "Question text",
            "options": [
                "Option A",
                "Option B",
                "Option C",
                "Option D"
            ],
            "answer": "Correct Option"
        }}
    ]
}}
"""

    try:
        response = model.generate_content(prompt)

        text = response.text.strip()

        if text.startswith("```json"):
            text = text.replace("```json", "")
            text = text.replace("```", "")
            text = text.strip()

        data = json.loads(text)

        return data["questions"]

    except Exception as e:
        print("Quiz Error:", e)

        return []
 


# Suggestion Function
def get_suggestion(tasks):
    for task in tasks:
        if task[2] == "Pending":
            return "Focus on: " + task[1]

    return "All tasks completed!"


# Home Page
@app.route("/")
def home():
    conn = sqlite3.connect("planner.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tasks")
    tasks = cursor.fetchall()

    conn.close()

    suggestion = get_suggestion(tasks)
    recommendation = get_daily_recommendation()

    return render_template(
        "index.html",
        tasks=tasks,
        suggestion=suggestion,
        recommendation=recommendation
    )


# Add Task
@app.route("/add", methods=["POST"])
def add():
    task = request.form["task"]

    result = get_priority(task)
    difficulty = result["difficulty"]
    study_hours = result["study_hours"]
    reason = result["reason"]

    conn = sqlite3.connect("planner.db")
    cursor = conn.cursor()
    
    

    cursor.execute(
    """
    INSERT INTO tasks
    (task, status, difficulty, study_hours, reason)
    VALUES (?, ?, ?, ?, ?)
    """,
    (task, "Pending", difficulty, study_hours, reason)
)

    conn.commit()
    conn.close()

    return redirect("/")
@app.route("/quiz/<int:id>")
def quiz(id):

    conn = sqlite3.connect("planner.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT task FROM tasks WHERE id=?",
        (id,)
    )

    topic = cursor.fetchone()[0]

    conn.close()

    questions = generate_quiz(topic)

    print("Questions generated:", questions)

    return render_template(
        "quiz.html",
        topic=topic,
        questions=questions,
        task_id=id
    )
@app.route("/submit_quiz/<int:id>", methods=["POST"])
def submit_quiz(id):

    score = 0

    total = 5

    for i in range(5):

        user_answer = request.form.get(f"q{i}")

        correct_answer = request.form.get(
            f"answer{i}"
        )

        if user_answer == correct_answer:
            score += 1

    if score <= 2:
        level = "Beginner"

    elif score <= 4:
        level = "Intermediate"

    else:
        level = "Advanced"

    conn = sqlite3.connect("planner.db")

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE tasks
        SET score=?,
            level=?
        WHERE id=?
        """,
        (score * 20, level, id)
    )

    conn.commit()
    conn.close()

    return f"""
<h1>Quiz Result</h1>
<h2>Score: {score}/5</h2>
<h2>Level: {level}</h2>
<a href='/'>Go Home</a>
"""

def get_study_plan(topic, level):

    prompt = f"""
    Create a study plan.

    Topic: {topic}
    Level: {level}

    Return JSON only:

    {{
        "daily_hours": 2,
        "plan": [
            "Step 1",
            "Step 2",
            "Step 3"
        ]
    }}
    """

    try:
        response = model.generate_content(prompt)

        return json.loads(response.text)

    except:
        return {
            "daily_hours": 2,
            "plan": [
                "Practice basics",
                "Solve problems",
                "Revise concepts"
            ]
        }
def get_weak_topics():

    conn = sqlite3.connect("planner.db")

    cursor = conn.cursor()

    cursor.execute("""
    SELECT task
    FROM tasks
    WHERE level='Beginner'
    """)

    weak_topics = cursor.fetchall()

    conn.close()

    return weak_topics
def get_daily_recommendation():

    weak_topics = get_weak_topics()

    if weak_topics:

        return (
            "Focus on "
            + weak_topics[0][0]
            + " today"
        )

    return "Continue advanced practice"

@app.route("/studyplan/<int:id>")
def studyplan(id):

    conn = sqlite3.connect("planner.db")

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT task, level
        FROM tasks
        WHERE id=?
        """,
        (id,)
    )

    topic, level = cursor.fetchone()

    conn.close()

    plan = get_study_plan(
        topic,
        level
    )

    return render_template(
        "studyplan.html",
        topic=topic,
        level=level,
        plan=plan
    )

# Mark Completed
@app.route("/complete/<int:id>")
def complete(id):
    conn = sqlite3.connect("planner.db")
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE tasks SET status='Completed' WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect("/")


# Delete Task
@app.route("/delete/<int:id>")
def delete(id):
    conn = sqlite3.connect("planner.db")
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM tasks WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)