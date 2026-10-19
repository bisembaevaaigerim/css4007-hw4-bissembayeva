import ast

MAX_NUMBER = 1e15

def check_number(x):
    if isinstance(x, complex):
        raise ValueError("result is not a real number")
    if abs(x) > MAX_NUMBER:
        raise ValueError("number too large: result is bigger than 1e15")
    return x


def count(node):
    if isinstance(node, ast.Constant):
        if type(node.value) == int or type(node.value) == float:
            return check_number(node.value)
        raise ValueError("not allowed: only numbers, + - * / ** and brackets")

    if isinstance(node, ast.UnaryOp):
        x = count(node.operand)
        if isinstance(node.op, ast.USub):
            return -x
        if isinstance(node.op, ast.UAdd):
            return x
        raise ValueError("not allowed: only numbers, + - * / ** and brackets")

    if isinstance(node, ast.BinOp):
        a = count(node.left)
        b = count(node.right)

        if isinstance(node.op, ast.Add):
            result = a + b
        elif isinstance(node.op, ast.Sub):
            result = a - b
        elif isinstance(node.op, ast.Mult):
            result = a * b
        elif isinstance(node.op, ast.Div):
            if b == 0:
                raise ValueError("division by zero")
            result = a / b
        elif isinstance(node.op, ast.Pow):
            if abs(b) > 10:
                raise ValueError("number too large: exponent must be between -10 and 10")
            result = a ** b
        else:
            raise ValueError("not allowed: only numbers, + - * / ** and brackets")

        return check_number(result)
    raise ValueError("not allowed: only numbers, + - * / ** and brackets")


def calculate(expression):
    if type(expression) != str:
        return {"error": "expression must be 1 to 200 characters"}

    expression = expression.strip()
    if len(expression) == 0 or len(expression) > 200:
        return {"error": "expression must be 1 to 200 characters"}

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return {"error": "invalid syntax"}
    except Exception:
        return {"error": "expression too complex"}

    try:
        result = count(tree.body)
    except ValueError as e:
        return {"error": str(e)}
    except ZeroDivisionError:
        return {"error": "division by zero"}
    except OverflowError:
        return {"error": "number too large: result is bigger than 1e15"}
    except RecursionError:
        return {"error": "expression too complex"}
    except Exception as e:
        return {"error": "calculate failed: " + str(type(e).__name__)}

    return {"expression": expression, "result": result}





import difflib
import json
import os
import re


DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "corpus.jsonl")

DISTRICTS = ["Ossbridge", "Ossford", "Tarnvale", "Kelmarsh", "Brightwater", "Stonecairn",
             "Harrowfield", "Lindenmoor", "Redfen", "Ashgrove", "Millbrook", "Coldharbour"]

NUM = r"(\d[\d,]*(?:\.\d+)?)"

PATTERNS = {
    "population_2025": [r"2025 census (?:recorded|counted) " + NUM, NUM + r" in 2025"],
    "population_2020": [r"2020 census had recorded " + NUM, NUM + r" in 2020", NUM + r" at the 2020 census"],
    "area_km2": [NUM + r" square kilometres"],
    "budget_2025_million_tenge": [NUM + r" million tenge"],
    "water_use_2025_megalitres": [NUM + r" (megalitres|cubic metres)"],
    "schools": [NUM + r" schools"],
    "pupils_2025_26": [NUM + r" pupils"],
    "paved_road_km": [NUM + r" km of paved road", NUM + r" km long"],
    "founded_year": [r"[Ff]ounded in (\d{4})"],
}

UNITS = {
    "population_2025": "residents",
    "population_2020": "residents",
    "area_km2": "km2",
    "budget_2025_million_tenge": "million tenge",
    "water_use_2025_megalitres": "megalitres",
    "schools": "schools",
    "pupils_2025_26": "pupils",
    "paved_road_km": "km",
    "founded_year": "year",
    "water_tariff_2025": "tenge per m3",
}

CORRECTION_WORDS = {
    "area_km2": "area",
    "population_2025": "population",
    "budget_2025_million_tenge": "budget",
    "water_use_2025_megalitres": "water use",
    "schools": "number of schools",
    "pupils_2025_26": "number of pupils",
    "paved_road_km": "road length",
    "founded_year": "founding year",
}

ALL_FIELDS = list(UNITS.keys())


def load_documents():
    documents = []
    with open(DATA_FILE, encoding="utf-8") as f:
        for line in f:
            if line.strip() != "":
                documents.append(json.loads(line))
    return documents


DOCUMENTS = load_documents()


def to_number(text):
    text = text.replace(",", "")
    if "." in text:
        return float(text)
    return int(text)

# evidence
def find_sentence(text, piece):
    sentences = re.split(r"(?<=\.)\s+", text)
    for sentence in sentences:
        if piece in sentence:
            return sentence
    return ""

#STEP3
def check_district(name):
    if type(name) != str or name.strip() == "" or len(name) > 50:
        return None, "district must be a district name, for example Brightwater"
    name = name.strip()

    for district in DISTRICTS:
        if district.lower() == name.lower():
            return district, None

    starts_same = [d for d in DISTRICTS if d.lower().startswith(name.lower())]
    if len(starts_same) >= 2:
        return None, name + " is not a full district name; did you mean " + " or ".join(starts_same) + "?"

    similar = difflib.get_close_matches(name, DISTRICTS, n=2, cutoff=0.5)
    for d in starts_same:
        if d not in similar:
            similar.insert(0, d)
    if len(similar) > 0:
        return None, "no district named " + name + "; did you mean " + " or ".join(similar[:2]) + "?"
    return None, "no district named " + name + "; districts are: " + ", ".join(DISTRICTS)

#STEP4
def find_profile(district):
    current = []
    for doc in DOCUMENTS:
        title = doc["title"]
        if title.startswith(district + " district profile") and "ARCHIVED" not in title:
            current.append(doc)
    if len(current) == 0:
        return None, "no current profile for " + district + "; archived profiles are not used"
    if len(current) > 1:
        ids = [doc["id"] for doc in current]
        return None, "conflicting profiles for " + district + ": " + " and ".join(ids)
    return current[0], None

#STEP5
def read_field(doc, field):
    for pattern in PATTERNS[field]:
        match = re.search(pattern, doc["text"])
        if match:
            value = to_number(match.group(1))
            sentence = find_sentence(doc["text"], match.group(0))
            raw_unit = None
            if field == "water_use_2025_megalitres":
                raw_unit = match.group(2)   
            return value, raw_unit, sentence, None
    return None, None, None, "field " + field + " not found in " + doc["id"]

#STEP6
def apply_correction(district, field, value):
    if field not in CORRECTION_WORDS:
        return value, None, ""
    for doc in DOCUMENTS:
        if doc["title"].startswith("Correction notice") and district in doc["title"]:
            word = CORRECTION_WORDS[field]
            match = re.search(r"correct " + word + r" is " + NUM, doc["text"])
            if match:
                new_value = to_number(match.group(1))
                note = doc["id"] + " corrects " + str(value) + " to " + str(new_value)
                return new_value, doc["id"], note
    return value, None, ""

#STEP7
def fix_unit(field, value, raw_unit):
    if field != "water_use_2025_megalitres":
        return value, ""
    if raw_unit == "megalitres":
        return value, ""
    if raw_unit == "cubic metres":
        return value / 1000, "changed from " + str(value) + " cubic metres"
    raise ValueError("unknown unit for " + field)


def water_tariff():
    for doc in DOCUMENTS:
        match = re.search(r"2025 the regional household water tariff is " + NUM + r" tenge per cubic metre", doc["text"])
        if match:
            sentence = find_sentence(doc["text"], match.group(0))
            return {"district": "Region", "field": "water_tariff_2025", "value": to_number(match.group(1)),
                    "unit": "tenge per m3", "source": doc["id"], "corrected_by": None,
                    "note": "the same in every district", "evidence": sentence}
    return {"error": "water tariff not found"}


def lookup(district, field):
    try:
        if field not in ALL_FIELDS:
            return {"error": "unknown field " + str(field) + "; allowed fields are: " + ", ".join(ALL_FIELDS)}

        if type(district) == str and district.strip().lower() == "region":
            if field == "water_tariff_2025":
                return water_tariff()
            return {"error": "Region can only be used with water_tariff_2025"}
        if field == "water_tariff_2025":
            return water_tariff()

        name, error = check_district(district)
        if error:
            return {"error": error}

        doc, error = find_profile(name)
        if error:
            return {"error": error}

        value, raw_unit, sentence, error = read_field(doc, field)
        if error:
            return {"error": error}

        value, corrected_by, note = apply_correction(name, field, value)

        value, unit_note = fix_unit(field, value, raw_unit)
        if unit_note != "":
            note = unit_note

        return {
            "district": name,
            "field": field,
            "value": value,
            "unit": UNITS[field],
            "source": doc["id"],
            "corrected_by": corrected_by,
            "note": note,
            "evidence": sentence,
        }
    except Exception as e:
        return {"error": "lookup failed: " + str(e)}