"""
IronLog — Suivi musculation + cycle + enhancement
Architecture: Flask + PostgreSQL + Jinja2 (même pattern que Budget App)
"""
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import json, os, hashlib, uuid
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "ironlog-secret-key-change-me")

DATABASE_URL = os.environ.get("DATABASE_URL", "")
PASSWORD_HASH = os.environ.get("PASSWORD_HASH", hashlib.sha256("ironlog2026".encode()).hexdigest())
ENH_PIN_HASH = os.environ.get("ENH_PIN_HASH", "")  # set after first PIN creation


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS sessions_log (
        id BIGSERIAL PRIMARY KEY,
        date TEXT, muscle TEXT, exercise TEXT,
        sets JSONB, estimated_1rm REAL, total_volume REAL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS encours (
        id BIGSERIAL PRIMARY KEY,
        session_uid TEXT, date TEXT, muscle TEXT, exercise TEXT,
        set_number INT, reps INT, weight REAL,
        saved_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS prs (
        exercise TEXT PRIMARY KEY, estimated_1rm REAL, updated_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)""")
    conn.commit(); cur.close(); conn.close()


# ═══════════════════════════════════════════════════════════
# EXERCISE DATABASE
# ═══════════════════════════════════════════════════════════
MUSCLES = [
    {"id": "poitrine", "label": "Poitrine", "emoji": "🏋️"},
    {"id": "dos", "label": "Dos", "emoji": "💪"},
    {"id": "epaules", "label": "Épaules", "emoji": "🦾"},
    {"id": "biceps", "label": "Biceps", "emoji": "💪"},
    {"id": "triceps", "label": "Triceps", "emoji": "⚡"},
    {"id": "jambes", "label": "Jambes", "emoji": "🦵"},
    {"id": "abdos", "label": "Abdos", "emoji": "🔥"},
]

EXO = {
    "poitrine": [
        {"id": "dc", "n": "Développé couché", "v": ["Barre libre", "Haltères", "Barre Smith", "Technogym", "Hammer Strength", "Hammer Strength debout", "Machine Noire"]},
        {"id": "di", "n": "Développé incliné", "v": ["Barre libre", "Haltères", "Technogym", "Hammer Strength", "Barre Smith", "Machine Noire"]},
        {"id": "dd", "n": "Développé décliné", "v": ["Haltères", "Barre libre", "Barre Smith"]},
        {"id": "ec", "n": "Écarté", "v": ["Haltères plat", "Haltères incliné", "Pec-Deck Technogym", "Câble croisé bas", "Câble croisé haut", "Câble croisé milieu"]},
        {"id": "dp", "n": "Dips poitrine", "v": ["Barres parallèles", "Lest ceinture"]},
        {"id": "po", "n": "Pullover", "v": ["Haltère", "Barre EZ", "Câble barre haute", "Câble poulie haute"]},
    ],
    "dos": [
        {"id": "tr", "n": "Traction", "v": ["Prise large pronation", "Prise large marteau", "Prise marteau", "Prise supination", "Technogym pronation", "Hammer Strength supination", "Traction ceinture", "Machine Noire"]},
        {"id": "tp", "n": "Tirage poitrine", "v": ["Prise large pronation", "Prise neutre", "Prise supination"]},
        {"id": "rp", "n": "Rowing barre / poulie", "v": ["Barre pronation", "Barre supination", "Prise marteau", "Haltère unilatéral", "Hammer Strength", "Machine Noire", "Câble bas", "Barre libre pronation", "Barre libre supination", "Corde poulie bas"]},
        {"id": "sd", "n": "Soulevé de terre", "v": ["Barre conventionnel", "Barre sumo", "Haltères", "Roumain barre", "Roumain haltères"]},
        {"id": "hy", "n": "Extension lombaire", "v": ["Poids du corps", "Haltère", "Barre", "Machine Technogym", "Disque"]},
        {"id": "rt", "n": "Rowing T-bar", "v": ["Machine T-bar", "Barre + poignée", "Hammer Strength"]},
        {"id": "rc", "n": "Rowing câble bas", "v": ["Poignée V", "Barre large", "Unilatéral câble"]},
    ],
    "epaules": [
        {"id": "dm", "n": "Développé militaire", "v": ["Barre libre debout", "Barre libre assis", "Barre Smith", "Haltères debout", "Haltères assis", "Technogym", "Hammer Strength", "Hammer Strength debout", "Arnold press", "Machine Noire Technogym"]},
        {"id": "el", "n": "Élévations latérales", "v": ["Haltères debout", "Haltères assis", "Câble bas unilatéral", "Hammer Strength Jaune", "Machine Technogym Noire", "Pec-Deck inversée"]},
        {"id": "oi", "n": "Oiseau / Rear delt", "v": ["Haltères debout", "Haltères assis", "Câble poulie haute corde", "Pec-Deck inversée Technogym"]},
        {"id": "ef", "n": "Élévations frontales", "v": ["Haltères alternés", "Haltères bilatéral", "Barre libre", "Disque", "Poulie barre", "Poulie câble"]},
        {"id": "sh", "n": "Trapèze / Shrug", "v": ["Haltères", "Barre", "Barre Smith", "Câble poulie haute corde", "Câble barre poulie"]},
        {"id": "fp", "n": "Face pull", "v": ["Câble poulie haute corde", "Câble poulie milieu corde", "Bande élastique"]},
    ],
    "biceps": [
        {"id": "cu", "n": "Curl", "v": ["Barre droite", "Barre EZ prise large", "Barre EZ prise serrée", "Câble bas barre droite", "Câble bas barre EZ", "Câble bas poignée", "Câble bas corde", "Haltères alterné debout", "Haltères bilatéral debout", "Haltères assis alterné", "Haltères concentré", "Haltères incliné", "Technogym"]},
        {"id": "cm", "n": "Curl marteau", "v": ["Haltères alterné", "Haltères bilatéral", "Câble corde"]},
        {"id": "ci", "n": "Curl inverse", "v": ["Barre EZ", "Haltères"]},
        {"id": "wc", "n": "Wrist curl", "v": ["Poulie", "Barre", "Haltères"]},
    ],
    "triceps": [
        {"id": "bf", "n": "Barre au front", "v": ["Barre droite", "Barre EZ", "Haltères", "Câble poulie haute barre", "Câble poulie haute corde"]},
        {"id": "ex", "n": "Extension câble", "v": ["Corde poulie haute", "Barre droite poulie haute", "Barre V poulie haute", "Unilatéral poulie haute", "Corde poulie basse", "Kickback câble"]},
        {"id": "dt", "n": "Dips triceps", "v": ["Banc dips poids corps", "Technogym", "Barres parallèles lest"]},
        {"id": "ds", "n": "Développé serré", "v": ["Barre", "Barre Smith", "Haltères"]},
    ],
    "jambes": [
        {"id": "sq", "n": "Squat", "v": ["Barre libre", "Barre Smith", "Hammer Strength"]},
        {"id": "pr", "n": "Presse", "v": ["Technogym", "Hammer Strength", "Presse machine horizontale", "Presse verticale Hammer Smith", "Hack squat machine"]},
        {"id": "fn", "n": "Fentes", "v": ["Haltères marchées", "Barre marchées", "Statiques haltères", "Bulgares barre", "Bulgares haltères", "Barre Smith"]},
        {"id": "lc", "n": "Leg curl", "v": ["Assis Technogym", "Allongé Technogym"]},
        {"id": "le", "n": "Leg extension", "v": ["Technogym Jaune", "Technogym Noire"]},
        {"id": "mo", "n": "Mollets", "v": ["Machine assis Technogym", "Presse machine mollets", "Barre Smith", "Donkey calf raise", "Unilatéral"]},
        {"id": "rd", "n": "RDL / Deadlift roumain", "v": ["Barre", "Haltères"]},
        {"id": "ht", "n": "Hip thrust", "v": ["Barre libre", "Barre Smith", "Haltères"]},
        {"id": "abd", "n": "Abduction", "v": ["Machine Technogym Noire"]},
        {"id": "add", "n": "Adduction", "v": ["Machine Technogym Noire"]},
    ],
    "abdos": [
        {"id": "cr", "n": "Crunch", "v": ["Sol", "Hammer Strength", "Câble poulie haute corde", "Crunch inversé"]},
        {"id": "rj", "n": "Relevé de jambes", "v": ["Suspendu barre fixe", "Barres parallèles", "Banc décliné"]},
        {"id": "pl", "n": "Planche", "v": ["Avant", "Côté gauche", "Côté droit"]},
        {"id": "ra", "n": "Rouleau abdominal", "v": ["Ab wheel genoux", "Ab wheel debout"]},
        {"id": "wo", "n": "Woodchop", "v": ["Poulie haut-bas", "Poulie bas-haut"]},
        {"id": "co", "n": "Crunch oblique", "v": ["Poulie haute"]},
    ],
}

EXO_BY_ID = {}
for mid, exos in EXO.items():
    for ex in exos:
        EXO_BY_ID[ex["id"]] = {**ex, "muscle": mid}


# ═══════════════════════════════════════════════════════════
# PROGRAM TEMPLATES LIBRARY
# Ces templates sont codés en dur ici — ils ne dépendent JAMAIS de la base
# de données. Même si la BDD est perdue, les programmes restent intacts.
# "Démarrer un programme" crée une COPIE indépendante dans training_cycles,
# donc plusieurs cycles (et plusieurs instances du même programme) peuvent
# coexister sans jamais s'écraser.
# ═══════════════════════════════════════════════════════════

PROGRAM_PPL16 = {
    "template_id": "tpl_ppl16",
    "name": "PPL x2 — 16 Semaines",
    "description": "Push/Pull/Legs x2 par semaine, alternance Force/Hypertrophie",
    "sessions": [
        {"id": "pull1", "name": "Lundi — PULL 1 (Force)", "exos": [
            {"name": "Soulevé de terre — Barre conventionnel", "sets": 5, "reps": 5, "rest": 180, "dw": 120},
            {"name": "Tirage poitrine — Prise large pronation", "sets": 5, "reps": 5, "rest": 180, "dw": 65},
            {"name": "Rowing barre / poulie — Barre pronation", "sets": 4, "reps": 6, "rest": 180, "dw": 60},
            {"name": "Curl — Barre EZ prise large", "sets": 4, "reps": 7, "rest": 150, "dw": 30},
            {"name": "Rouleau abdominal — Ab wheel genoux", "sets": 4, "reps": 10, "rest": 90, "dw": 0},
            {"name": "Curl inverse — Barre EZ", "sets": 4, "reps": 9, "rest": 90, "dw": 15},
            {"name": "Woodchop — Poulie haut-bas", "sets": 3, "reps": 12, "rest": 90, "dw": 15},
            {"name": "Wrist curl — Poulie", "sets": 4, "reps": 11, "rest": 90, "dw": 10},
        ]},
        {"id": "push1", "name": "Mercredi — PUSH 1 (Force)", "exos": [
            {"name": "Développé couché — Barre libre", "sets": 5, "reps": 5, "rest": 180, "dw": 90},
            {"name": "Développé incliné — Barre libre", "sets": 4, "reps": 6, "rest": 180, "dw": 70},
            {"name": "Dips poitrine — Lest ceinture", "sets": 4, "reps": 6, "rest": 180, "dw": 10},
            {"name": "Développé militaire — Barre libre assis", "sets": 5, "reps": 5, "rest": 180, "dw": 50},
            {"name": "Élévations latérales — Haltères debout", "sets": 4, "reps": 10, "rest": 120, "dw": 14},
            {"name": "Barre au front — Barre EZ", "sets": 4, "reps": 7, "rest": 150, "dw": 40},
            {"name": "Rouleau abdominal — Ab wheel genoux", "sets": 4, "reps": 10, "rest": 90, "dw": 0},
        ]},
        {"id": "legs1", "name": "Jeudi — LEGS 1 (Force)", "exos": [
            {"name": "Squat — Barre libre", "sets": 5, "reps": 5, "rest": 180, "dw": 90},
            {"name": "Presse — Technogym", "sets": 4, "reps": 7, "rest": 180, "dw": 200},
            {"name": "RDL / Deadlift roumain — Barre", "sets": 4, "reps": 7, "rest": 120, "dw": 80},
            {"name": "Mollets — Machine assis Technogym", "sets": 5, "reps": 9, "rest": 120, "dw": 60},
            {"name": "Leg curl — Allongé Technogym", "sets": 4, "reps": 7, "rest": 150, "dw": 75},
            {"name": "Hip thrust — Barre libre", "sets": 4, "reps": 8, "rest": 120, "dw": 80},
            {"name": "Mollets — Presse machine mollets", "sets": 4, "reps": 13, "rest": 120, "dw": 40},
            {"name": "Extension lombaire — Disque", "sets": 4, "reps": 11, "rest": 90, "dw": 20},
        ]},
        {"id": "pull2", "name": "Vendredi — PULL 2 (Hypertrophie)", "exos": [
            {"name": "Tirage poitrine — Prise neutre", "sets": 4, "reps": 11, "rest": 150, "dw": 60},
            {"name": "Rowing barre / poulie — Haltère unilatéral", "sets": 4, "reps": 11, "rest": 120, "dw": 30},
            {"name": "Pullover — Câble poulie haute", "sets": 3, "reps": 13, "rest": 90, "dw": 25},
            {"name": "Curl — Haltères incliné", "sets": 3, "reps": 13, "rest": 90, "dw": 14},
            {"name": "Curl marteau — Haltères alterné", "sets": 3, "reps": 13, "rest": 120, "dw": 18},
            {"name": "Curl inverse — Haltères", "sets": 4, "reps": 13, "rest": 90, "dw": 10},
            {"name": "Wrist curl — Poulie", "sets": 3, "reps": 15, "rest": 60, "dw": 10},
            {"name": "Woodchop — Poulie bas-haut", "sets": 3, "reps": 15, "rest": 90, "dw": 15},
        ]},
        {"id": "push2", "name": "Samedi — PUSH 2 (Hypertrophie)", "exos": [
            {"name": "Développé couché — Haltères", "sets": 4, "reps": 11, "rest": 150, "dw": 36},
            {"name": "Développé incliné — Haltères", "sets": 4, "reps": 11, "rest": 150, "dw": 30},
            {"name": "Écarté — Câble croisé bas", "sets": 3, "reps": 15, "rest": 90, "dw": 12},
            {"name": "Écarté — Pec-Deck Technogym", "sets": 3, "reps": 15, "rest": 90, "dw": 40},
            {"name": "Développé militaire — Haltères assis", "sets": 4, "reps": 11, "rest": 150, "dw": 28},
            {"name": "Élévations latérales — Câble bas unilatéral", "sets": 4, "reps": 15, "rest": 90, "dw": 8},
            {"name": "Oiseau / Rear delt — Haltères debout", "sets": 4, "reps": 15, "rest": 90, "dw": 10},
            {"name": "Extension câble — Corde poulie haute", "sets": 3, "reps": 13, "rest": 90, "dw": 20},
            {"name": "Crunch — Hammer Strength", "sets": 4, "reps": 13, "rest": 90, "dw": 40},
            {"name": "Crunch oblique — Poulie haute", "sets": 3, "reps": 15, "rest": 60, "dw": 15},
        ]},
        {"id": "legs2", "name": "Dimanche — LEGS 2 (Hypertrophie)", "exos": [
            {"name": "Presse — Hack squat machine", "sets": 4, "reps": 11, "rest": 150, "dw": 100},
            {"name": "Leg extension — Technogym Jaune", "sets": 3, "reps": 13, "rest": 90, "dw": 60},
            {"name": "Leg curl — Allongé Technogym", "sets": 4, "reps": 13, "rest": 120, "dw": 60},
            {"name": "Hip thrust — Haltères", "sets": 4, "reps": 15, "rest": 90, "dw": 30},
            {"name": "Mollets — Donkey calf raise", "sets": 4, "reps": 17, "rest": 90, "dw": 40},
            {"name": "Mollets — Unilatéral", "sets": 3, "reps": 17, "rest": 90, "dw": 20},
            {"name": "Extension lombaire — Disque", "sets": 3, "reps": 13, "rest": 90, "dw": 15},
        ]},
    ],
}

PROGRAM_ONEMUSCLE = {
    "template_id": "tpl_onemuscle",
    "name": "One Muscle Per Session — 6 jours",
    "description": "Un groupe musculaire dédié par séance, volume élevé, fréquence 1x/semaine",
    "sessions": [
        {"id": "om_chest", "name": "Lundi — Poitrine", "exos": [
            {"name": "Développé couché — Barre libre", "sets": 5, "reps": 6, "rest": 150, "dw": 90},
            {"name": "Développé incliné — Haltères", "sets": 4, "reps": 10, "rest": 120, "dw": 32},
            {"name": "Écarté — Pec-Deck Technogym", "sets": 4, "reps": 12, "rest": 90, "dw": 40},
            {"name": "Dips poitrine — Barres parallèles", "sets": 3, "reps": 10, "rest": 120, "dw": 0},
            {"name": "Pullover — Câble poulie haute", "sets": 3, "reps": 12, "rest": 90, "dw": 25},
        ]},
        {"id": "om_back", "name": "Mardi — Dos", "exos": [
            {"name": "Soulevé de terre — Barre conventionnel", "sets": 5, "reps": 5, "rest": 180, "dw": 120},
            {"name": "Traction — Prise large pronation", "sets": 4, "reps": 8, "rest": 150, "dw": 0},
            {"name": "Rowing barre / poulie — Barre pronation", "sets": 4, "reps": 10, "rest": 120, "dw": 55},
            {"name": "Tirage poitrine — Prise neutre", "sets": 4, "reps": 12, "rest": 90, "dw": 55},
            {"name": "Extension lombaire — Disque", "sets": 3, "reps": 12, "rest": 90, "dw": 15},
        ]},
        {"id": "om_legs", "name": "Mercredi — Jambes", "exos": [
            {"name": "Squat — Barre libre", "sets": 5, "reps": 6, "rest": 180, "dw": 90},
            {"name": "Presse — Technogym", "sets": 4, "reps": 10, "rest": 150, "dw": 180},
            {"name": "RDL / Deadlift roumain — Barre", "sets": 4, "reps": 10, "rest": 120, "dw": 70},
            {"name": "Leg extension — Technogym Jaune", "sets": 3, "reps": 15, "rest": 90, "dw": 55},
            {"name": "Leg curl — Allongé Technogym", "sets": 3, "reps": 15, "rest": 90, "dw": 60},
            {"name": "Mollets — Machine assis Technogym", "sets": 4, "reps": 15, "rest": 60, "dw": 55},
        ]},
        {"id": "om_shoulders", "name": "Jeudi — Épaules", "exos": [
            {"name": "Développé militaire — Barre libre debout", "sets": 5, "reps": 6, "rest": 150, "dw": 45},
            {"name": "Élévations latérales — Haltères debout", "sets": 4, "reps": 12, "rest": 90, "dw": 12},
            {"name": "Oiseau / Rear delt — Haltères debout", "sets": 4, "reps": 12, "rest": 90, "dw": 8},
            {"name": "Élévations frontales — Disque", "sets": 3, "reps": 12, "rest": 90, "dw": 10},
            {"name": "Trapèze / Shrug — Haltères", "sets": 3, "reps": 12, "rest": 90, "dw": 30},
        ]},
        {"id": "om_arms", "name": "Vendredi — Bras", "exos": [
            {"name": "Curl — Barre EZ prise large", "sets": 4, "reps": 10, "rest": 90, "dw": 28},
            {"name": "Barre au front — Barre EZ", "sets": 4, "reps": 10, "rest": 90, "dw": 35},
            {"name": "Curl marteau — Haltères alterné", "sets": 3, "reps": 12, "rest": 90, "dw": 16},
            {"name": "Extension câble — Corde poulie haute", "sets": 3, "reps": 12, "rest": 90, "dw": 20},
            {"name": "Curl inverse — Barre EZ", "sets": 3, "reps": 12, "rest": 60, "dw": 15},
            {"name": "Dips triceps — Banc dips poids corps", "sets": 3, "reps": 12, "rest": 60, "dw": 0},
        ]},
        {"id": "om_abs", "name": "Samedi — Abdos & Mollets", "exos": [
            {"name": "Crunch — Hammer Strength", "sets": 4, "reps": 15, "rest": 60, "dw": 40},
            {"name": "Relevé de jambes — Suspendu barre fixe", "sets": 4, "reps": 12, "rest": 60, "dw": 0},
            {"name": "Rouleau abdominal — Ab wheel genoux", "sets": 3, "reps": 12, "rest": 60, "dw": 0},
            {"name": "Mollets — Machine debout Technogym Jaune", "sets": 4, "reps": 15, "rest": 60, "dw": 60},
        ]},
    ],
}

PROGRAMS_LIBRARY = [PROGRAM_PPL16, PROGRAM_ONEMUSCLE]
PROGRAMS_BY_ID = {p["template_id"]: p for p in PROGRAMS_LIBRARY}


def instantiate_program(template_id, start_date):
    """Crée une copie indépendante d'un template comme nouveau cycle actif.
    Ne touche JAMAIS aux autres cycles existants — ils restent dans
    training_cycles et gardent tout leur historique (log)."""
    tpl = PROGRAMS_BY_ID.get(template_id)
    if not tpl:
        return None
    return {
        "id": f"cyc{uuid.uuid4().hex[:10]}",
        "name": tpl["name"],
        "template_id": template_id,
        "start_date": start_date,
        "sessions": json.loads(json.dumps(tpl["sessions"])),  # deep copy
        "log": [],
    }


# ═══════════════════════════════════════════════════════════
# ENHANCEMENT PRELOADED CYCLES
# ═══════════════════════════════════════════════════════════
def gen_injections(start_str, weeks, freq_days, products):
    start = datetime.strptime(start_str, "%Y-%m-%d").date()
    end = start + timedelta(weeks=weeks)
    injections = []
    cur = start
    idx = 0
    while cur <= end:
        if cur.weekday() in freq_days:
            injections.append({
                "id": f"inj{idx}", "date": cur.isoformat(), "done": False, "products": products
            })
            idx += 1
        cur += timedelta(days=1)
    return injections


def gen_daily_injections(start_str, end_str, products):
    start = datetime.strptime(start_str, "%Y-%m-%d").date()
    end = datetime.strptime(end_str, "%Y-%m-%d").date()
    injections = []
    cur = start
    idx = 0
    while cur <= end:
        injections.append({"id": f"d{idx}", "date": cur.isoformat(), "done": False, "products": products})
        idx += 1
        cur += timedelta(days=1)
    return injections


STEROID_PRODUCTS = [
    {"name": "Testostérone E", "dose": "250", "unit": "mg"},
    {"name": "Boldenone", "dose": "200", "unit": "mg"},
    {"name": "Masteron", "dose": "200", "unit": "mg"},
]
GH_PRODUCTS = [{"name": "GH", "dose": "5", "unit": "UI"}]

PRELOADED_ENH_MAIN = {
    "id": "enh_main",
    "products": [
        {"name": "Testostérone E", "dose": "250", "unit": "mg", "form": "injection"},
        {"name": "Boldenone", "dose": "200", "unit": "mg", "form": "injection"},
        {"name": "Masteron", "dose": "200", "unit": "mg", "form": "injection"},
        {"name": "Arimidex", "dose": "0.25", "unit": "mg", "form": "oral"},
    ],
    "weeks": 16, "start_date": "2026-06-18", "freq_days": [0, 3],
    "injections": gen_injections("2026-06-18", 16, [0, 3], STEROID_PRODUCTS),
}

PRELOADED_ENH_GH = {
    "id": "enh_gh",
    "products": [{"name": "GH", "dose": "5", "unit": "UI", "form": "injection"}],
    "weeks": 26, "start_date": "2026-06-05", "freq_days": [0, 1, 2, 3, 4, 5, 6],
    "injections": gen_daily_injections("2026-06-05", "2026-12-03", GH_PRODUCTS),
}


# ═══════════════════════════════════════════════════════════
# DEFAULT CONFIG (training cycles + enhancement state, stored in DB)
# ═══════════════════════════════════════════════════════════
DEFAULT_CONFIG = {
    "training_cycles": [instantiate_program("tpl_ppl16", "2026-06-08")],
    "active_cycle": None,  # set below
    "enh_cycles": [PRELOADED_ENH_MAIN, PRELOADED_ENH_GH],
    "active_enh": PRELOADED_ENH_MAIN["id"],
    "enh_pin_hash": "",
    "active_session": None,  # {cycle_id, session_id, exo_idx, set_idx, log: []}
}
DEFAULT_CONFIG["active_cycle"] = DEFAULT_CONFIG["training_cycles"][0]["id"]


def load_config():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT value FROM config WHERE key='main'")
        row = cur.fetchone(); cur.close(); conn.close()
        if row:
            cfg = json.loads(row[0])
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
    except Exception:
        pass
    return json.loads(json.dumps(DEFAULT_CONFIG))


def save_config(cfg):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO config (key,value) VALUES ('main',%s) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
        (json.dumps(cfg, ensure_ascii=False),)
    )
    conn.commit(); cur.close(); conn.close()


# ═══════════════════════════════════════════════════════════
# DB HELPERS
# ═══════════════════════════════════════════════════════════
def est_1rm(w, r):
    if r == 1:
        return w
    return round(w * (1 + r / 30), 1)


def get_sessions(limit=200):
    conn = get_conn(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM sessions_log ORDER BY created_at DESC LIMIT %s", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def get_prs():
    conn = get_conn(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM prs")
    rows = {r["exercise"]: r["estimated_1rm"] for r in cur.fetchall()}
    cur.close(); conn.close()
    return rows


def update_pr(exercise, rm):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO prs (exercise, estimated_1rm, updated_at) VALUES (%s,%s,NOW())
        ON CONFLICT (exercise) DO UPDATE SET
            estimated_1rm = GREATEST(prs.estimated_1rm, EXCLUDED.estimated_1rm),
            updated_at = CASE WHEN EXCLUDED.estimated_1rm > prs.estimated_1rm THEN NOW() ELSE prs.updated_at END
    """, (exercise, rm))
    conn.commit(); cur.close(); conn.close()


def save_session_db(date, muscle, exercise, sets, rm, vol):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO sessions_log (date,muscle,exercise,sets,estimated_1rm,total_volume) VALUES (%s,%s,%s,%s,%s,%s)",
        (date, muscle, exercise, json.dumps(sets, ensure_ascii=False), rm, vol)
    )
    conn.commit(); cur.close(); conn.close()


def get_last_session_for_exercise(exercise):
    conn = get_conn(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM sessions_log WHERE exercise=%s ORDER BY created_at DESC LIMIT 1", (exercise,))
    row = cur.fetchone(); cur.close(); conn.close()
    return dict(row) if row else None


def add_set_encours(session_uid, date, muscle, exercise, set_number, reps, weight):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO encours (session_uid,date,muscle,exercise,set_number,reps,weight) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (session_uid, date, muscle, exercise, set_number, reps, weight)
    )
    conn.commit(); cur.close(); conn.close()


def clear_encours():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("DELETE FROM encours")
    conn.commit(); cur.close(); conn.close()


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def fmt_date_fr(d):
    try:
        dt = datetime.strptime(d, "%Y-%m-%d")
        return dt.strftime("%d/%m/%y")
    except Exception:
        return d


# ═══════════════════════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════════════════════
def is_logged_in():
    return session.get("logged_in", False)


@app.before_request
def require_login():
    if request.endpoint in ("login", "static"):
        return
    if not is_logged_in():
        return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pwd = request.form.get("password", "")
        if hashlib.sha256(pwd.encode()).hexdigest() == PASSWORD_HASH:
            session["logged_in"] = True
            return redirect(url_for("index"))
        return render_template("login.html", error="Mot de passe incorrect")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ═══════════════════════════════════════════════════════════
# MAIN ROUTES
# ═══════════════════════════════════════════════════════════
@app.route("/")
def index():
    return redirect(url_for("cycle_home"))


@app.route("/seances")
def seances():
    sessions_list = get_sessions()
    for s in sessions_list:
        s["sets"] = s["sets"] if isinstance(s["sets"], list) else json.loads(s["sets"])
    return render_template("seances.html", sessions=sessions_list)


@app.route("/stats")
def stats():
    sessions_list = get_sessions()
    prs = get_prs()
    total_vol = sum(s.get("total_volume") or 0 for s in sessions_list)
    by_date = {}
    for s in sessions_list:
        by_date[s["date"]] = by_date.get(s["date"], 0) + (s.get("total_volume") or 0)
    chart_data = sorted(by_date.items())[-10:]
    max_vol = max([v for _, v in chart_data], default=1)
    return render_template(
        "stats.html",
        total_sessions=len(sessions_list),
        total_volume=round(total_vol / 1000, 1),
        prs=sorted(prs.items(), key=lambda x: -x[1])[:12],
        chart_data=[(fmt_date_fr(d)[:5], v, round((v / max_vol) * 90)) for d, v in chart_data],
    )


# ═══════════════════════════════════════════════════════════
# CYCLE ROUTES
# ═══════════════════════════════════════════════════════════
@app.route("/cycle")
def cycle_home():
    cfg = load_config()
    active = next((c for c in cfg["training_cycles"] if c["id"] == cfg["active_cycle"]), None)
    others = [c for c in cfg["training_cycles"] if c["id"] != cfg["active_cycle"]]
    for c in cfg["training_cycles"]:
        c["start_date_fr"] = fmt_date_fr(c["start_date"])
    return render_template("cycle_home.html", active=active, others=others, active_session=cfg.get("active_session"))


@app.route("/cycle/activate/<cycle_id>")
def cycle_activate(cycle_id):
    cfg = load_config()
    cfg["active_cycle"] = cycle_id
    save_config(cfg)
    return redirect(url_for("cycle_home"))


@app.route("/cycle/<cycle_id>")
def cycle_detail(cycle_id):
    cfg = load_config()
    cyc = next((c for c in cfg["training_cycles"] if c["id"] == cycle_id), None)
    if not cyc:
        return redirect(url_for("cycle_home"))
    log = cyc.get("log", [])
    weeks = 0
    try:
        start = datetime.strptime(cyc["start_date"], "%Y-%m-%d")
        weeks = max(0, (datetime.now() - start).days // 7)
    except Exception:
        pass
    total_exos = sum(len(s["exos"]) for s in cyc["sessions"])
    for s in cyc["sessions"]:
        s["preview"] = ", ".join(f"{e['sets']}×{e['reps']}" for e in s["exos"])
    return render_template("cycle_detail.html", cyc=cyc, total_sessions=len(log), weeks=weeks, total_exos=total_exos)


@app.route("/cycle/<cycle_id>/start/<session_id>")
def cycle_start_session(cycle_id, session_id):
    cfg = load_config()
    cyc = next((c for c in cfg["training_cycles"] if c["id"] == cycle_id), None)
    if not cyc:
        return redirect(url_for("cycle_home"))
    ses = next((s for s in cyc["sessions"] if s["id"] == session_id), None)
    if not ses:
        return redirect(url_for("cycle_detail", cycle_id=cycle_id))
    # New free-order structure: track each exo independently
    cfg["active_session"] = {
        "cycle_id": cycle_id, "session_id": session_id,
        "session_uid": f"sess-{uuid.uuid4().hex[:10]}",
        "exo_idx": 0, "set_idx": 0, "log": [],
        "exo_sets_done": {},   # {exo_name: [sets done so far]}
        "exo_done": [],        # list of completed exo names
        "current_exo": None,   # exo name being filled right now
        "current_set": 0,      # set index for current exo
    }
    save_config(cfg)
    return redirect(url_for("cycle_session"))


@app.route("/cycle/session")
def cycle_session():
    cfg = load_config()
    act = cfg.get("active_session")
    if not act:
        return redirect(url_for("cycle_home"))
    cyc = next((c for c in cfg["training_cycles"] if c["id"] == act["cycle_id"]), None)
    ses = next((s for s in cyc["sessions"] if s["id"] == act["session_id"]), None)

    # If an exo is currently being filled → show the set entry screen
    current_exo_name = act.get("current_exo")
    if current_exo_name:
        exo = next((e for e in ses["exos"] if e["name"] == current_exo_name), None)
        if exo:
            sets_done = act.get("exo_sets_done", {}).get(current_exo_name, [])
            current_set = act.get("current_set", 0)
            is_last_set = current_set >= exo["sets"] - 1

            last_session = get_last_session_for_exercise(exo["name"])
            last_sets = []
            default_weight = exo.get("dw", 60)
            if last_session:
                last_sets = last_session["sets"] if isinstance(last_session["sets"], list) else json.loads(last_session["sets"])
                if current_set < len(last_sets):
                    default_weight = last_sets[current_set]["weight"]
            if sets_done:
                default_weight = sets_done[-1]["weight"]
                default_reps = sets_done[-1]["reps"]
            else:
                default_reps = exo["reps"]

            return render_template(
                "cycle_session.html",
                ses=ses, exo=exo, act=act,
                sets_done=sets_done,
                current_set=current_set,
                is_last_set=is_last_set,
                last_sets=last_sets,
                default_weight=default_weight, default_reps=default_reps,
                progress_dots=range(exo["sets"]),
                mode="filling",
            )

    # Otherwise → show the free-order exo list
    exo_done = act.get("exo_done", [])
    exo_sets_done = act.get("exo_sets_done", {})
    all_done = all(e["name"] in exo_done for e in ses["exos"])

    if all_done:
        # Session complete
        if "log" not in cyc:
            cyc["log"] = []
        cyc["log"].append({"date": today_str(), "session_name": ses["name"], "sets": act["log"]})
        cfg["active_session"] = None
        clear_encours()
        save_config(cfg)
        return redirect(url_for("cycle_detail", cycle_id=act["cycle_id"]))

    return render_template(
        "cycle_session.html",
        ses=ses, act=act,
        exo_done=exo_done, exo_sets_done=exo_sets_done,
        mode="list",
    )


@app.route("/cycle/session/pick/<path:exo_name>")
def cycle_session_pick(exo_name):
    """User picks which exo to do — free order."""
    cfg = load_config()
    act = cfg.get("active_session")
    if not act:
        return redirect(url_for("cycle_home"))
    if exo_name in act.get("exo_done", []):
        return redirect(url_for("cycle_session"))
    act["current_exo"] = exo_name
    act["current_set"] = 0
    cfg["active_session"] = act
    save_config(cfg)
    return redirect(url_for("cycle_session"))


@app.route("/cycle/session/save", methods=["POST"])
def cycle_session_save():
    cfg = load_config()
    act = cfg.get("active_session")
    if not act:
        return redirect(url_for("cycle_home"))
    cyc = next((c for c in cfg["training_cycles"] if c["id"] == act["cycle_id"]), None)
    ses = next((s for s in cyc["sessions"] if s["id"] == act["session_id"]), None)
    exo_name = act.get("current_exo")
    exo = next((e for e in ses["exos"] if e["name"] == exo_name), None)
    if not exo:
        return redirect(url_for("cycle_session"))

    reps = int(request.form.get("reps", 0))
    weight = float(request.form.get("weight", 0))
    current_set = act.get("current_set", 0)
    set_num = current_set + 1

    if "exo_sets_done" not in act:
        act["exo_sets_done"] = {}
    act["exo_sets_done"].setdefault(exo_name, []).append({"reps": reps, "weight": weight})
    act["log"].append({"exo": exo_name, "set": set_num, "reps": reps, "weight": weight})

    rm = est_1rm(weight, reps)
    update_pr(exo_name, rm)
    add_set_encours(act["session_uid"], today_str(), ses["name"], exo_name, set_num, reps, weight)

    is_last_set = current_set >= exo["sets"] - 1
    if is_last_set:
        sets_clean = act["exo_sets_done"][exo_name]
        exo_rm = max(est_1rm(s["weight"], s["reps"]) for s in sets_clean)
        exo_vol = round(sum(s["weight"] * s["reps"] for s in sets_clean), 1)
        save_session_db(today_str(), ses["name"], exo_name, sets_clean, exo_rm, exo_vol)
        if "exo_done" not in act:
            act["exo_done"] = []
        act["exo_done"].append(exo_name)
        act["current_exo"] = None
        act["current_set"] = 0
    else:
        act["current_set"] = current_set + 1

    cfg["active_session"] = act
    save_config(cfg)
    return redirect(url_for("cycle_session"))


@app.route("/cycle/session/skip")
def cycle_session_skip():
    """Skip current exo — mark as done without saving sets."""
    cfg = load_config()
    act = cfg.get("active_session")
    if act and act.get("current_exo"):
        if "exo_done" not in act:
            act["exo_done"] = []
        act["exo_done"].append(act["current_exo"])
        act["current_exo"] = None
        act["current_set"] = 0
        cfg["active_session"] = act
        save_config(cfg)
    return redirect(url_for("cycle_session"))


@app.route("/cycle/session/quit")
def cycle_session_quit():
    cfg = load_config()
    act = cfg.get("active_session")
    cycle_id = act.get("cycle_id") if act else None

    if act:
        # Si l'exercice en cours a des sets déjà validés mais pas encore
        # complet (set_idx > 0 et pas encore tous les sets), on les
        # sauvegarde quand même dans l'historique permanent avant de
        # quitter. Rien n'est jamais perdu, même un exercice abandonné
        # en plein milieu.
        cyc = next((c for c in cfg["training_cycles"] if c["id"] == act["cycle_id"]), None)
        if cyc:
            ses = next((s for s in cyc["sessions"] if s["id"] == act["session_id"]), None)
            if ses and act.get("current_exo"):
                cur_exo_name = act["current_exo"]
                cur_exo = next((e for e in ses["exos"] if e["name"] == cur_exo_name), None)
                pending_sets = act.get("exo_sets_done", {}).get(cur_exo_name, [])
                if pending_sets and cur_exo:
                    sets_clean = [{"reps": s["reps"], "weight": s["weight"]} for s in pending_sets]
                    rm = max(est_1rm(s["weight"], s["reps"]) for s in sets_clean)
                    vol = round(sum(s["weight"] * s["reps"] for s in sets_clean), 1)
                    save_session_db(today_str(), ses["name"], cur_exo["name"], sets_clean, rm, vol)

    cfg["active_session"] = None
    save_config(cfg)
    clear_encours()
    if cycle_id:
        return redirect(url_for("cycle_detail", cycle_id=cycle_id))
    return redirect(url_for("cycle_home"))


@app.route("/cycle/<cycle_id>/stats")
def cycle_stats(cycle_id):
    cfg = load_config()
    cyc = next((c for c in cfg["training_cycles"] if c["id"] == cycle_id), None)
    if not cyc:
        return redirect(url_for("cycle_home"))

    # Liste des exercices de ce cycle
    cycle_exo_names = set()
    all_exos = {}
    for s in cyc["sessions"]:
        for ex in s["exos"]:
            all_exos.setdefault(ex["name"], [])
            cycle_exo_names.add(ex["name"])

    # Détermine si une date donnée tombe dans une période d'enhancement actif
    # (seul lien visible entre les deux systèmes, qui restent par ailleurs
    # totalement indépendants : dates de début, durées, et logique séparées)
    enh_periods = []
    for ec in cfg.get("enh_cycles", []):
        try:
            start = datetime.strptime(ec["start_date"], "%Y-%m-%d").date()
            end = start + timedelta(weeks=ec["weeks"])
            enh_periods.append((start, end, ec["products"][0]["name"] if ec["products"] else "Cycle"))
        except Exception:
            pass

    def in_enhancement(date_str):
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
            for start, end, name in enh_periods:
                if start <= d <= end:
                    return name
        except Exception:
            pass
        return None

    # Source de vérité : sessions_log (mise à jour en temps réel, exercice
    # par exercice — pas besoin d'attendre la fin de toute la séance pour
    # voir la progression).
    rows = get_sessions(1000)
    rows = [r for r in rows if r["exercise"] in cycle_exo_names]
    rows.sort(key=lambda r: str(r.get("created_at") or r["date"]))
    for r in rows:
        sets = r["sets"] if isinstance(r["sets"], list) else json.loads(r["sets"])
        if not sets:
            continue
        avg_w = round(sum(s["weight"] for s in sets) / len(sets), 1)
        avg_r = round(sum(s["reps"] for s in sets) / len(sets), 1)
        enh_tag = in_enhancement(r["date"])
        all_exos[r["exercise"]].append({
            "date": r["date"], "avg_weight": avg_w, "avg_reps": avg_r, "enh_tag": enh_tag
        })

    selected = request.args.get("exo")
    selected_points = all_exos.get(selected, []) if selected else []

    comparison = None
    if len(selected_points) > 1:
        first, last = selected_points[0], selected_points[-1]
        dw = round(last["avg_weight"] - first["avg_weight"], 1)
        dr = round(last["avg_reps"] - first["avg_reps"], 1)
        comparison = {"last_w": last["avg_weight"], "last_r": last["avg_reps"], "dw": dw, "dr": dr}

    return render_template(
        "cycle_stats.html", cyc=cyc, all_exos=all_exos,
        selected=selected, selected_points=selected_points, comparison=comparison,
    )


@app.route("/cycle/library")
def cycle_library():
    """Bibliothèque de programmes — codés en dur, jamais perdus même si la BDD saute."""
    return render_template("cycle_library.html", programs=PROGRAMS_LIBRARY, today=today_str())


@app.route("/cycle/library/start", methods=["POST"])
def cycle_library_start():
    template_id = request.form.get("template_id")
    start_date = request.form.get("start_date", today_str())
    new_cycle = instantiate_program(template_id, start_date)
    if not new_cycle:
        return redirect(url_for("cycle_library"))
    cfg = load_config()
    cfg["training_cycles"].append(new_cycle)
    cfg["active_cycle"] = new_cycle["id"]
    save_config(cfg)
    return redirect(url_for("cycle_detail", cycle_id=new_cycle["id"]))


@app.route("/cycle/create", methods=["GET", "POST"])
def cycle_create():
    cfg = load_config()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        sessions_json = request.form.get("sessions_json", "[]")
        try:
            sessions_data = json.loads(sessions_json)
        except Exception:
            sessions_data = []
        if name and sessions_data:
            new_cycle = {
                "id": f"cyc{uuid.uuid4().hex[:10]}",
                "name": name, "start_date": today_str(),
                "sessions": sessions_data, "log": [],
            }
            cfg["training_cycles"].append(new_cycle)
            cfg["active_cycle"] = new_cycle["id"]
            save_config(cfg)
            return redirect(url_for("cycle_detail", cycle_id=new_cycle["id"]))
    return render_template("cycle_create.html", muscles=MUSCLES, exo=EXO)


# ═══════════════════════════════════════════════════════════
# ENHANCEMENT ROUTES
# ═══════════════════════════════════════════════════════════
def enh_unlocked():
    return session.get("enh_unlocked", False)


@app.route("/enhancement")
def enhancement_home():
    cfg = load_config()
    if not cfg.get("enh_pin_hash"):
        return render_template("enh_setpin.html")
    if not enh_unlocked():
        return render_template("enh_pin.html")
    active = next((c for c in cfg["enh_cycles"] if c["id"] == cfg["active_enh"]), None)
    others = [c for c in cfg["enh_cycles"] if c["id"] != cfg["active_enh"]]
    next_inj = None
    if active:
        today = today_str()
        upcoming = [i for i in active["injections"] if not i["done"] and i["date"] >= today]
        if upcoming:
            next_inj = sorted(upcoming, key=lambda x: x["date"])[0]
            next_inj["date_fr"] = fmt_date_fr(next_inj["date"])
            next_inj["is_today"] = next_inj["date"] == today
    for c in [active] + others if active else others:
        if c:
            c["start_date_fr"] = fmt_date_fr(c["start_date"])
    return render_template("enh_home.html", active=active, others=others, next_inj=next_inj)


@app.route("/enhancement/setpin", methods=["POST"])
def enh_setpin():
    pin = request.form.get("pin", "")
    cfg = load_config()
    cfg["enh_pin_hash"] = hashlib.sha256(pin.encode()).hexdigest()
    save_config(cfg)
    session["enh_unlocked"] = True
    return redirect(url_for("enhancement_home"))


@app.route("/enhancement/unlock", methods=["POST"])
def enh_unlock():
    pin = request.form.get("pin", "")
    cfg = load_config()
    if hashlib.sha256(pin.encode()).hexdigest() == cfg.get("enh_pin_hash"):
        session["enh_unlocked"] = True
        return redirect(url_for("enhancement_home"))
    return render_template("enh_pin.html", error="PIN incorrect")


@app.route("/enhancement/lock")
def enh_lock():
    session["enh_unlocked"] = False
    return redirect(url_for("enhancement_home"))


@app.route("/enhancement/<cycle_id>")
def enh_detail(cycle_id):
    if not enh_unlocked():
        return redirect(url_for("enhancement_home"))
    cfg = load_config()
    cyc = next((c for c in cfg["enh_cycles"] if c["id"] == cycle_id), None)
    if not cyc:
        return redirect(url_for("enhancement_home"))
    injections = sorted(cyc["injections"], key=lambda x: x["date"])
    today = today_str()
    for i in injections:
        i["date_fr"] = fmt_date_fr(i["date"])
        i["is_today"] = i["date"] == today
    done_count = sum(1 for i in cyc["injections"] if i["done"])
    return render_template("enh_detail.html", cyc=cyc, injections=injections, done_count=done_count)


@app.route("/enhancement/<cycle_id>/mark/<inj_id>")
def enh_mark_done(cycle_id, inj_id):
    if not enh_unlocked():
        return redirect(url_for("enhancement_home"))
    cfg = load_config()
    cyc = next((c for c in cfg["enh_cycles"] if c["id"] == cycle_id), None)
    if cyc:
        inj = next((i for i in cyc["injections"] if i["id"] == inj_id), None)
        if inj:
            inj["done"] = True
            inj["done_at"] = datetime.now().isoformat()
        save_config(cfg)
    return redirect(request.referrer or url_for("enhancement_home"))


@app.route("/enhancement/create", methods=["GET", "POST"])
def enh_create():
    if not enh_unlocked():
        return redirect(url_for("enhancement_home"))
    if request.method == "POST":
        products_json = request.form.get("products_json", "[]")
        try:
            products = json.loads(products_json)
        except Exception:
            products = []
        weeks = int(request.form.get("weeks", 12))
        start_date = request.form.get("start_date", today_str())
        freq_days = [int(d) for d in request.form.getlist("freq_days")]

        has_inj = any(p.get("form") == "injection" for p in products)
        injections = []
        if has_inj and freq_days:
            simple_products = [{"name": p["name"], "dose": p["dose"], "unit": p["unit"]} for p in products]
            injections = gen_injections(start_date, weeks, freq_days, simple_products)

        cfg = load_config()
        new_cycle = {
            "id": f"enh{uuid.uuid4().hex[:10]}",
            "products": products, "weeks": weeks, "start_date": start_date,
            "freq_days": freq_days, "injections": injections,
        }
        cfg["enh_cycles"].append(new_cycle)
        cfg["active_enh"] = new_cycle["id"]
        save_config(cfg)
        return redirect(url_for("enh_detail", cycle_id=new_cycle["id"]))
    return render_template("enh_create.html", today=today_str())


# ═══════════════════════════════════════════════════════════
# EXERCISE PICKER (used by cycle_create via AJAX-like navigation)
# ═══════════════════════════════════════════════════════════
@app.route("/exo_picker")
def exo_picker():
    return jsonify(EXO)


# ═══════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════
@app.route("/export")
def export_json():
    sessions_list = get_sessions(1000)
    for s in sessions_list:
        s["sets"] = s["sets"] if isinstance(s["sets"], list) else json.loads(s["sets"])
        ca = s["created_at"]
        s["created_at"] = ca.isoformat() if hasattr(ca, "isoformat") else (ca if ca else None)
    cfg = load_config()
    data = {
        "export_date": datetime.now().isoformat(),
        "sessions": sessions_list,
        "training_cycles": cfg["training_cycles"],
    }
    return jsonify(data)


@app.route("/settings")
def settings():
    sessions_list = get_sessions()
    prs = get_prs()
    return render_template("settings.html", total_sessions=len(sessions_list), total_prs=len(prs))


@app.route("/settings/reset_pin")
def reset_pin():
    cfg = load_config()
    cfg["enh_pin_hash"] = ""
    save_config(cfg)
    session["enh_unlocked"] = False
    return redirect(url_for("settings"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
else:
    try:
        init_db()
    except Exception:
        pass
