"""Exercise library and Renaissance Periodization volume landmarks.

Landmarks are weekly working-set counts per muscle group:
    MV   maintenance volume
    MEV  minimum effective volume
    MAV  maximum adaptive volume (midpoint of the productive range)
    MRV  maximum recoverable volume
Values follow RP's published hypertrophy guidelines for an intermediate
lifter; they can be overridden per-athlete in the profile.
"""

# muscle: (MV, MEV, MAV, MRV)
LANDMARKS = {
    "chest":      (4, 8, 16, 22),
    "back":       (6, 10, 18, 25),
    "quads":      (4, 8, 14, 20),
    "hamstrings": (3, 6, 12, 16),
    "glutes":     (0, 4, 10, 16),
    "shoulders":  (4, 8, 16, 22),
    "biceps":     (4, 8, 14, 20),
    "triceps":    (4, 8, 12, 18),
    "calves":     (4, 8, 12, 16),
    "abs":        (0, 6, 12, 20),
    "traps":      (0, 4, 10, 16),
    "forearms":   (0, 2, 8, 12),
}

MUSCLES = list(LANDMARKS)


def _ex(primary, secondary=(), equipment="barbell", joint=0.4,
        region="upper", compound=True, alts=()):
    return {
        "primary": list(primary), "secondary": list(secondary),
        "equipment": equipment, "joint": joint, "region": region,
        "compound": compound, "alts": list(alts),
    }


EXERCISES = {
    # --- chest ---------------------------------------------------------
    "Bench Press": _ex(["chest"], ["triceps", "shoulders"], "barbell", 0.5,
                       alts=["DB Bench Press", "Machine Chest Press",
                             "Push-Up"]),
    "Incline Press": _ex(["chest"], ["shoulders", "triceps"], "barbell", 0.5,
                         alts=["Incline DB Press", "Machine Chest Press"]),
    "DB Bench Press": _ex(["chest"], ["triceps", "shoulders"], "dumbbell",
                          0.4, alts=["Machine Chest Press", "Push-Up"]),
    "Incline DB Press": _ex(["chest"], ["shoulders", "triceps"], "dumbbell",
                            0.4, alts=["Machine Chest Press"]),
    "Machine Chest Press": _ex(["chest"], ["triceps"], "machine", 0.2,
                               alts=["Push-Up"]),
    "Cable Fly": _ex(["chest"], [], "cable", 0.2, compound=False,
                     alts=["Pec Deck", "DB Fly"]),
    "Pec Deck": _ex(["chest"], [], "machine", 0.2, compound=False,
                    alts=["Cable Fly"]),
    "DB Fly": _ex(["chest"], [], "dumbbell", 0.3, compound=False,
                  alts=["Cable Fly", "Pec Deck"]),
    "Push-Up": _ex(["chest"], ["triceps", "shoulders"], "bodyweight", 0.2,
                   alts=["Machine Chest Press"]),
    # --- back ---------------------------------------------------------
    "Barbell Row": _ex(["back"], ["biceps", "traps"], "barbell", 0.5,
                       alts=["Chest-Supported Row", "Cable Row",
                             "DB Row"]),
    "DB Row": _ex(["back"], ["biceps"], "dumbbell", 0.3,
                  alts=["Cable Row", "Chest-Supported Row"]),
    "Chest-Supported Row": _ex(["back"], ["biceps"], "machine", 0.2,
                               alts=["Cable Row"]),
    "Cable Row": _ex(["back"], ["biceps"], "cable", 0.2,
                     alts=["Chest-Supported Row"]),
    "Pull-Up": _ex(["back"], ["biceps"], "bodyweight", 0.4,
                   alts=["Lat Pulldown", "Assisted Pull-Up"]),
    "Assisted Pull-Up": _ex(["back"], ["biceps"], "machine", 0.3,
                            alts=["Lat Pulldown"]),
    "Lat Pulldown": _ex(["back"], ["biceps"], "cable", 0.2,
                        alts=["Pull-Up", "Assisted Pull-Up"]),
    "Deadlift": _ex(["back", "hamstrings"], ["glutes", "traps", "forearms"],
                    "barbell", 0.7, region="lower",
                    alts=["Trap Bar Deadlift", "Romanian Deadlift"]),
    "Trap Bar Deadlift": _ex(["back", "quads"], ["glutes", "traps"],
                             "barbell", 0.6, region="lower",
                             alts=["Romanian Deadlift"]),
    # --- shoulders / traps ---------------------------------------------
    "Overhead Press": _ex(["shoulders"], ["triceps"], "barbell", 0.5,
                          alts=["DB Shoulder Press", "Machine Shoulder Press"]),
    "DB Shoulder Press": _ex(["shoulders"], ["triceps"], "dumbbell", 0.4,
                             alts=["Machine Shoulder Press"]),
    "Machine Shoulder Press": _ex(["shoulders"], ["triceps"], "machine", 0.2,
                                  alts=["DB Shoulder Press"]),
    "Lateral Raise": _ex(["shoulders"], [], "dumbbell", 0.2, compound=False,
                         alts=["Cable Lateral Raise"]),
    "Cable Lateral Raise": _ex(["shoulders"], [], "cable", 0.2,
                               compound=False, alts=["Lateral Raise"]),
    "Rear Delt Fly": _ex(["shoulders"], ["back"], "dumbbell", 0.15,
                         compound=False, alts=["Face Pull"]),
    "Face Pull": _ex(["shoulders"], ["traps"], "cable", 0.1, compound=False,
                     alts=["Rear Delt Fly"]),
    "Barbell Shrug": _ex(["traps"], ["forearms"], "barbell", 0.3,
                         compound=False, alts=["DB Shrug"]),
    "DB Shrug": _ex(["traps"], ["forearms"], "dumbbell", 0.2,
                    compound=False, alts=["Barbell Shrug"]),
    # --- arms ------------------------------------------------------------
    "Barbell Curl": _ex(["biceps"], ["forearms"], "barbell", 0.3,
                        compound=False, alts=["DB Curl", "Cable Curl"]),
    "DB Curl": _ex(["biceps"], ["forearms"], "dumbbell", 0.2,
                   compound=False, alts=["Cable Curl", "Hammer Curl"]),
    "Hammer Curl": _ex(["biceps"], ["forearms"], "dumbbell", 0.2,
                       compound=False, alts=["Cable Curl"]),
    "Cable Curl": _ex(["biceps"], [], "cable", 0.15, compound=False,
                      alts=["DB Curl"]),
    "Skullcrusher": _ex(["triceps"], [], "barbell", 0.4, compound=False,
                        alts=["Cable Pushdown", "Overhead Extension"]),
    "Cable Pushdown": _ex(["triceps"], [], "cable", 0.15, compound=False,
                          alts=["Overhead Extension"]),
    "Overhead Extension": _ex(["triceps"], [], "cable", 0.25,
                              compound=False, alts=["Cable Pushdown"]),
    "Dips": _ex(["triceps", "chest"], ["shoulders"], "bodyweight", 0.5,
                alts=["Cable Pushdown", "Machine Chest Press"]),
    "Wrist Curl": _ex(["forearms"], [], "dumbbell", 0.15, compound=False),
    # --- lower body ----------------------------------------------------
    "Back Squat": _ex(["quads", "glutes"], ["hamstrings", "abs"], "barbell",
                      0.6, region="lower",
                      alts=["Hack Squat", "Leg Press", "Safety Bar Squat",
                            "Goblet Squat"]),
    "Safety Bar Squat": _ex(["quads", "glutes"], ["hamstrings"], "barbell",
                            0.45, region="lower",
                            alts=["Hack Squat", "Leg Press"]),
    "Front Squat": _ex(["quads"], ["glutes", "abs"], "barbell", 0.55,
                       region="lower", alts=["Hack Squat", "Leg Press"]),
    "Hack Squat": _ex(["quads"], ["glutes"], "machine", 0.4, region="lower",
                      alts=["Leg Press"]),
    "Leg Press": _ex(["quads", "glutes"], [], "machine", 0.3,
                     region="lower", alts=["Goblet Squat"]),
    "Goblet Squat": _ex(["quads", "glutes"], [], "dumbbell", 0.3,
                        region="lower", alts=["Leg Press"]),
    "Romanian Deadlift": _ex(["hamstrings", "glutes"], ["back"], "barbell",
                             0.4, region="lower",
                             alts=["Leg Curl", "Good Morning"]),
    "Good Morning": _ex(["hamstrings"], ["back", "glutes"], "barbell", 0.5,
                        region="lower", alts=["Romanian Deadlift",
                                              "Leg Curl"]),
    "Leg Curl": _ex(["hamstrings"], [], "machine", 0.15, region="lower",
                    compound=False, alts=["Romanian Deadlift"]),
    "Leg Extension": _ex(["quads"], [], "machine", 0.25, region="lower",
                         compound=False, alts=["Leg Press"]),
    "Hip Thrust": _ex(["glutes"], ["hamstrings"], "barbell", 0.25,
                      region="lower", alts=["Romanian Deadlift"]),
    "Walking Lunge": _ex(["quads", "glutes"], ["hamstrings"], "dumbbell",
                         0.35, region="lower", alts=["Leg Press"]),
    "Standing Calf Raise": _ex(["calves"], [], "machine", 0.15,
                               region="lower", compound=False,
                               alts=["Seated Calf Raise"]),
    "Seated Calf Raise": _ex(["calves"], [], "machine", 0.1,
                             region="lower", compound=False,
                             alts=["Standing Calf Raise"]),
    # --- core --------------------------------------------------------------
    "Cable Crunch": _ex(["abs"], [], "cable", 0.15, compound=False,
                        alts=["Hanging Leg Raise", "Plank"]),
    "Hanging Leg Raise": _ex(["abs"], ["forearms"], "bodyweight", 0.2,
                             compound=False, alts=["Cable Crunch", "Plank"]),
    "Plank": _ex(["abs"], [], "bodyweight", 0.05, compound=False,
                 alts=["Cable Crunch"]),
}


def info(name):
    """Exercise record; unknown names get a sensible generic entry."""
    return EXERCISES.get(name) or _ex(["back"], [], "other", 0.3)


def increment(name, units):
    """Smallest sensible load jump for progression suggestions."""
    e = info(name)
    if units == "kg":
        return 5.0 if (e["compound"] and e["region"] == "lower") else \
               (2.5 if e["compound"] else 1.25)
    return 10.0 if (e["compound"] and e["region"] == "lower") else \
           (5.0 if e["compound"] else 2.5)


def swap_chain(name, equipment_available=None):
    """Ordered alternative exercises (for pain-driven swaps)."""
    out = []
    for alt in info(name)["alts"]:
        e = EXERCISES.get(alt)
        if e is None:
            continue
        if equipment_available and e["equipment"] not in equipment_available:
            continue
        out.append(alt)
    return out
