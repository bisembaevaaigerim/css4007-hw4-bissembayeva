import copy
import json
import os

from run import is_correct
from strategies import LOOKUP_TOOL, CALCULATE_TOOL, TOOLS, s3_tools

# the same lookup tool, only the description is one vague line
VAGUE_LOOKUP = copy.deepcopy(LOOKUP_TOOL)
VAGUE_LOOKUP["function"]["description"] = "Looks things up."
VAGUE_TOOLS = [VAGUE_LOOKUP, CALCULATE_TOOL]

QUESTION_IDS = ["Q-01", "Q-03", "Q-08", "Q-09", "Q-17"]
FOLDER = os.path.join("outputs", "c1")
LOG_FOLDER = os.path.join(FOLDER, "logs")

with open("data/questions.json", encoding="utf-8") as f:
    questions = [q for q in json.load(f) if q["id"] in QUESTION_IDS]

rows = []
for q in questions:
    for version, tool_list in [("mine", TOOLS), ("vague", VAGUE_TOOLS)]:
        r = s3_tools(q["question"], q["id"], tool_list=tool_list,
                     log_name="S3_" + version, log_folder=LOG_FOLDER)

        # read the log to see what the model sent to lookup and how many errors it got
        with open(os.path.join(LOG_FOLDER, "S3_" + version + "_" + q["id"] + ".json"), encoding="utf-8") as f:
            log = json.load(f)
        lookup_inputs = []
        errors = 0
        for rnd in log["rounds"]:
            for call in rnd["tool_calls"]:
                if "error" in call["result"]:
                    errors += 1
                if call["tool"] == "lookup":
                    lookup_inputs.append(call["arguments"])

        row = {
            "question": q["id"],
            "version": version,
            "model_calls": r["model_calls"],
            "tool_calls": r["tool_calls"],
            "tool_errors": errors,
            "input_tokens": r["input_tokens"],
            "answer": str(r["answer_name"]) + " | " + str(r["answer_number"]),
            "correct": is_correct(q, r["answer_name"], r["answer_number"]),
            "lookup_inputs": lookup_inputs,
        }
        rows.append(row)
        print(row["question"], row["version"].ljust(5), "| model calls:", row["model_calls"],
              "| tool calls:", row["tool_calls"], "| errors:", row["tool_errors"],
              "| answer:", row["answer"], "| correct:", row["correct"])

with open(os.path.join(FOLDER, "c1_results.json"), "w", encoding="utf-8") as f:
    json.dump(rows, f, indent=2, ensure_ascii=False)
print("saved to outputs/c1/c1_results.json")