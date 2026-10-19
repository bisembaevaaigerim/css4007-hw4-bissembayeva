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



def s3_tools(question, question_id, tool_list=TOOLS, log_name="S3"):
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
    save_log(log_name, question_id, log)
    return result