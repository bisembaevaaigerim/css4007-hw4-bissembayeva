import json
import os
import re
import time

from dotenv import load_dotenv
from openai import OpenAI

from tools import calculate, lookup

load_dotenv()               
client = OpenAI()             

MODEL = "gpt-5.6-luna"
MAX_ROUNDS = 8              
REASONING_EFFORT = "none"
K_SAMPLES = 5             
S2_TEMPERATURE = 1.0    

ANSWER_RULE = (
    "End your reply with exactly one line in this format:\n"
    "ANSWER: <district name or yes/no> | <number>\n"
    "Write the number with 3 decimals, no units and no commas, for example: ANSWER: Millbrook | 0.556"
)


LOOKUP_TOOL = {
    "type": "function",
    "function": {
        "name": "lookup",
        "description": (
            "Get ONE fact about ONE district of the Nine Rivers Region from the official 2025 profiles. "
            "Call it once for every number you need (for example, 2 districts x 2 fields = 4 calls). "
            "The 12 districts are: Ossbridge, Ossford, Tarnvale, Kelmarsh, Brightwater, Stonecairn, "
            "Harrowfield, Lindenmoor, Redfen, Ashgrove, Millbrook, Coldharbour. "
            "Be careful: Ossbridge and Ossford are different districts. "
            "The tool already skips old ARCHIVED profiles, applies correction notices and converts units, "
            "so the value you get is the one to use. Water use is always in megalitres. "
            "For the water price use district \"Region\" and field \"water_tariff_2025\". "
            "The result is JSON with these keys: value (the number to use), unit, source (document id), "
            "evidence (the sentence from the profile), corrected_by (id of the correction notice or null) "
            "and note (what was changed, for example a unit change). "
            "If the result has an \"error\" key, read it, fix your input and try again. "
            "Do not do maths yourself, use the calculate tool."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "district": {
                    "type": "string",
                    "description": "Exact district name, for example \"Brightwater\". Use \"Region\" only for water_tariff_2025.",
                },
                "field": {
                    "type": "string",
                    "enum": ["population_2025", "population_2020", "area_km2", "budget_2025_million_tenge",
                             "water_use_2025_megalitres", "schools", "pupils_2025_26", "paved_road_km",
                             "founded_year", "water_tariff_2025"],
                    "description": "Which fact you need.",
                },
            },
            "required": ["district", "field"],
            "additionalProperties": False,
        },
    },
}

CALCULATE_TOOL = {
    "type": "function",
    "function": {
        "name": "calculate",
        "description": (
            "Calculate an arithmetic expression exactly. Use it for EVERY calculation (divisions, differences, "
            "percentages, unit changes), never do maths in your head. Only numbers, + - * / ** and brackets "
            "are allowed, for example \"(52904 - 48317) / 48317 * 100\". Do not use commas inside numbers "
            "(write 1284.6, not 1,284.6). No variables, no functions, no text. The result is a number with "
            "full precision, do not round it before the final answer. If the result has an \"error\" key, "
            "fix the expression and try again."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Arithmetic expression, for example \"44675 / 921.4\".",
                },
            },
            "required": ["expression"],
            "additionalProperties": False,
        },
    },
}

TOOLS = [LOOKUP_TOOL, CALCULATE_TOOL]

S3_SYSTEM = (
    "You answer questions about the Nine Rivers Region, a made-up place. "
    "You do not have the documents. Get every fact with the lookup tool "
    "and do every calculation with the calculate tool.\n" + ANSWER_RULE
)

def documents_text():
    parts = []
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "corpus.jsonl"), encoding="utf-8") as f:
        for line in f:
            if line.strip() != "":
                doc = json.loads(line)
                parts.append("[" + doc["id"] + "] " + doc["title"] + "\n" + doc["text"])
    return "\n\n".join(parts)


DOCS_SYSTEM = (
    "You answer questions about the Nine Rivers Region, a made-up place. "
    "Use only the documents below.\n" + ANSWER_RULE + "\n\nDOCUMENTS:\n\n" + documents_text()
)

S2_THINK = "Think step by step: write down every fact you use with its document id, then do the calculation, then give the answer."

def find_answer(text):
    if text is None:
        return None, None
    matches = re.findall(r"ANSWER:\s*([^|\n]+?)\s*\|\s*([-\d.,]+)", text)
    if len(matches) == 0:
        return None, None
    name, number = matches[-1]
    try:
        number = float(number.replace(",", ""))
    except ValueError:
        number = None
    return name.strip(), number


def run_tool(name, arguments_text):
    try:
        args = json.loads(arguments_text)
    except (json.JSONDecodeError, TypeError):
        return {"error": "arguments are not valid JSON"}
    if type(args) != dict:
        return {"error": "arguments must be a JSON object"}

    if name == "lookup":
        if "district" not in args or "field" not in args:
            return {"error": "lookup needs district and field"}
        return lookup(args["district"], args["field"])
    if name == "calculate":
        if "expression" not in args:
            return {"error": "calculate needs expression"}
        return calculate(args["expression"])
    return {"error": "unknown tool " + str(name) + "; tools are lookup and calculate"}


def save_log(strategy, question_id, log, folder="outputs/logs"):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, strategy + "_" + question_id + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
    return path



def s3_tools(question, question_id, tool_list=TOOLS, log_name="S3", log_folder="outputs/logs"):
    messages = [
        {"role": "system", "content": S3_SYSTEM},
        {"role": "user", "content": question},
    ]
    log = {"question_id": question_id, "question": question, "model": MODEL, "rounds": []}
    input_tokens = 0
    output_tokens = 0
    start = time.time()
    final_text = None

    for round_number in range(1, MAX_ROUNDS + 1):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tool_list,
            reasoning_effort=REASONING_EFFORT,
        )
        input_tokens += response.usage.prompt_tokens
        output_tokens += response.usage.completion_tokens
        message = response.choices[0].message

        assistant_message = {"role": "assistant", "content": message.content}
        if message.tool_calls:
            assistant_message["tool_calls"] = [call.model_dump() for call in message.tool_calls]
        messages.append(assistant_message)

        round_log = {
            "round": round_number,
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "model_text": message.content,
            "tool_calls": [],
        }

        if not message.tool_calls:
            final_text = message.content
            log["rounds"].append(round_log)
            break

        for call in message.tool_calls:
            tool_start = time.time()
            result = run_tool(call.function.name, call.function.arguments)
            tool_seconds = time.time() - tool_start

            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False),
            })
            round_log["tool_calls"].append({
                "id": call.id,
                "tool": call.function.name,
                "arguments": call.function.arguments,
                "result": result,
                "seconds": round(tool_seconds, 6),
            })

        log["rounds"].append(round_log)

    name, number = find_answer(final_text)
    result = {
        "question_id": question_id,
        "final_text": final_text,
        "answer_name": name,
        "answer_number": number,
        "unanswered": final_text is None or name is None,
        "model_calls": len(log["rounds"]),
        "tool_calls": sum(len(r["tool_calls"]) for r in log["rounds"]),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "seconds": round(time.time() - start, 3),
    }
    if final_text is None:
        result["note"] = "stopped: reached the limit of " + str(MAX_ROUNDS) + " rounds"

    log["result"] = result
    log["messages"] = messages
    save_log(log_name, question_id, log, log_folder)
    return result

# ---------- S1: direct ----------

def s1_direct(question, question_id, log_folder="outputs/logs"):
    messages = [
        {"role": "system", "content": DOCS_SYSTEM},
        {"role": "user", "content": question},
    ]
    start = time.time()
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        reasoning_effort=REASONING_EFFORT,
    )
    seconds = time.time() - start
    text = response.choices[0].message.content
    name, number = find_answer(text)

    result = {
        "question_id": question_id,
        "final_text": text,
        "answer_name": name,
        "answer_number": number,
        "unanswered": name is None,
        "model_calls": 1,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "seconds": round(seconds, 3),
    }
    # the documents are the same for every question, so I do not save them in every log
    save_log("S1", question_id, {"question_id": question_id, "question": question, "model": MODEL,
                                 "result": result}, log_folder)
    return result


# ---------- S2: think step by step and vote ----------

def s2_vote(question, question_id, log_folder="outputs/logs"):
    messages = [
        {"role": "system", "content": DOCS_SYSTEM},
        {"role": "user", "content": question + "\n\n" + S2_THINK},
    ]
    samples = []
    input_tokens = 0
    output_tokens = 0
    start = time.time()
    temperature_used = S2_TEMPERATURE

    for i in range(K_SAMPLES):
        sample_start = time.time()
        settings = {"model": MODEL, "messages": messages, "reasoning_effort": REASONING_EFFORT}
        if temperature_used is not None:
            settings["temperature"] = temperature_used
        try:
            response = client.chat.completions.create(**settings)
        except Exception as e:
            # if the model does not allow temperature, ask again without it (this is saved in the log)
            if temperature_used is not None and "temperature" in str(e):
                temperature_used = None
                del settings["temperature"]
                response = client.chat.completions.create(**settings)
            else:
                raise
        input_tokens += response.usage.prompt_tokens
        output_tokens += response.usage.completion_tokens
        text = response.choices[0].message.content
        name, number = find_answer(text)
        samples.append({
            "sample": i + 1,
            "answer_name": name,
            "answer_number": number,
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "seconds": round(time.time() - sample_start, 3),
            "text": text,
        })

    # vote: count the same (name, number) pairs. Samples without an ANSWER line do not vote.
    votes = {}
    for s in samples:
        if s["answer_name"] is None or s["answer_number"] is None:
            continue
        key = (s["answer_name"].lower(), round(s["answer_number"], 3))
        if key not in votes:
            votes[key] = {"count": 0, "name": s["answer_name"], "number": s["answer_number"]}
        votes[key]["count"] += 1

    name = None
    number = None
    best = 0
    for key in votes:                      # if two answers have the same count, the first one wins
        if votes[key]["count"] > best:
            best = votes[key]["count"]
            name = votes[key]["name"]
            number = votes[key]["number"]

    result = {
        "question_id": question_id,
        "answer_name": name,
        "answer_number": number,
        "votes": str(best) + " of " + str(K_SAMPLES),
        "all_answers": [str(s["answer_name"]) + " | " + str(s["answer_number"]) for s in samples],
        "unanswered": name is None,
        "model_calls": K_SAMPLES,
        "temperature": temperature_used,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "seconds": round(time.time() - start, 3),
    }
    save_log("S2", question_id, {"question_id": question_id, "question": question, "model": MODEL,
                                 "result": result, "samples": samples}, log_folder)
    return result