"""Program templates. Nothing is hardcoded downstream — a program is plain
data (days -> exercise slots) and fully editable in the program editor."""
from .compat import clone


def slot(exercise, sets=3, lo=8, hi=12, tempo="2-0-1", notes=""):
    return {"exercise": exercise, "sets": sets, "reps": [lo, hi],
            "tempo": tempo, "notes": notes}


TEMPLATES = {
    "Upper Lower": {
        "days": [
            {"name": "Upper A", "exercises": [
                slot("Bench Press", 3, 6, 10),
                slot("Barbell Row", 3, 8, 12),
                slot("Overhead Press", 3, 8, 12),
                slot("Lat Pulldown", 3, 10, 15),
                slot("Lateral Raise", 3, 12, 20),
                slot("Cable Pushdown", 2, 10, 15),
            ]},
            {"name": "Lower A", "exercises": [
                slot("Back Squat", 3, 5, 8),
                slot("Romanian Deadlift", 3, 8, 12),
                slot("Leg Press", 3, 10, 15),
                slot("Leg Curl", 3, 10, 15),
                slot("Standing Calf Raise", 3, 10, 15),
                slot("Cable Crunch", 3, 10, 15),
            ]},
            {"name": "Upper B", "exercises": [
                slot("Incline Press", 3, 8, 12),
                slot("Pull-Up", 3, 6, 10),
                slot("DB Shoulder Press", 3, 8, 12),
                slot("Cable Row", 3, 10, 15),
                slot("DB Curl", 3, 10, 15),
                slot("Skullcrusher", 2, 10, 15),
            ]},
            {"name": "Lower B", "exercises": [
                slot("Deadlift", 3, 4, 6),
                slot("Hack Squat", 3, 8, 12),
                slot("Walking Lunge", 3, 10, 12),
                slot("Leg Extension", 3, 12, 15),
                slot("Seated Calf Raise", 3, 12, 20),
                slot("Hanging Leg Raise", 3, 8, 15),
            ]},
        ],
    },
    "Push Pull Legs": {
        "days": [
            {"name": "Push A", "exercises": [
                slot("Bench Press", 3, 6, 10),
                slot("Overhead Press", 3, 8, 12),
                slot("Incline DB Press", 3, 8, 12),
                slot("Lateral Raise", 3, 12, 20),
                slot("Cable Pushdown", 3, 10, 15),
            ]},
            {"name": "Pull A", "exercises": [
                slot("Barbell Row", 3, 8, 12),
                slot("Lat Pulldown", 3, 10, 15),
                slot("Face Pull", 3, 12, 20),
                slot("Barbell Curl", 3, 8, 12),
                slot("Hammer Curl", 2, 10, 15),
            ]},
            {"name": "Legs A", "exercises": [
                slot("Back Squat", 3, 5, 8),
                slot("Romanian Deadlift", 3, 8, 12),
                slot("Leg Press", 3, 10, 15),
                slot("Leg Curl", 3, 10, 15),
                slot("Standing Calf Raise", 4, 10, 15),
            ]},
            {"name": "Push B", "exercises": [
                slot("Incline Press", 3, 8, 12),
                slot("DB Bench Press", 3, 8, 12),
                slot("DB Shoulder Press", 3, 8, 12),
                slot("Cable Fly", 3, 12, 15),
                slot("Overhead Extension", 3, 10, 15),
            ]},
            {"name": "Pull B", "exercises": [
                slot("Pull-Up", 3, 6, 10),
                slot("Chest-Supported Row", 3, 10, 12),
                slot("Rear Delt Fly", 3, 12, 20),
                slot("DB Curl", 3, 10, 15),
                slot("Barbell Shrug", 3, 10, 15),
            ]},
            {"name": "Legs B", "exercises": [
                slot("Deadlift", 3, 4, 6),
                slot("Hack Squat", 3, 8, 12),
                slot("Walking Lunge", 3, 10, 12),
                slot("Leg Extension", 3, 12, 15),
                slot("Seated Calf Raise", 4, 12, 20),
            ]},
        ],
    },
    "Full Body": {
        "days": [
            {"name": "Full Body A", "exercises": [
                slot("Back Squat", 3, 5, 8),
                slot("Bench Press", 3, 6, 10),
                slot("Barbell Row", 3, 8, 12),
                slot("Lateral Raise", 3, 12, 20),
                slot("Cable Crunch", 3, 10, 15),
            ]},
            {"name": "Full Body B", "exercises": [
                slot("Deadlift", 3, 4, 6),
                slot("Overhead Press", 3, 8, 12),
                slot("Lat Pulldown", 3, 10, 15),
                slot("Leg Press", 3, 10, 15),
                slot("DB Curl", 3, 10, 15),
            ]},
            {"name": "Full Body C", "exercises": [
                slot("Hack Squat", 3, 8, 12),
                slot("Incline DB Press", 3, 8, 12),
                slot("Cable Row", 3, 10, 15),
                slot("Romanian Deadlift", 3, 8, 12),
                slot("Cable Pushdown", 3, 10, 15),
            ]},
        ],
    },
}


def make_program(template_name):
    """Instantiate an editable program from a template (deep copy)."""
    if template_name in TEMPLATES:
        prog = clone(TEMPLATES[template_name])
    else:
        prog = {"days": [{"name": "Day 1", "exercises": []}]}
    prog["name"] = template_name
    return prog
