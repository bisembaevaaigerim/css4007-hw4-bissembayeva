import argparse
import json
import os
import statistics
import time

from strategies import K_SAMPLES, MODEL, s1_direct, s2_vote, s3_tools

# price of gpt-5.6-luna in dollars for 1 million tokens (check it on the OpenAI pricing page)
PRICE_INPUT = 0.20
PRICE_OUTPUT = 1.20

STRATEGIES = {
    "S1": s1_direct,
    "S2": s2_vote,
    "S3": s3_tools,
}


def is_correct(question, name, number):
    # my rule (written before the first full run):
    # 1) the name must be the same (big/small letters do not matter)
    # 2) the number rounded to the question's decimals must be equal to "value",
    #    a difference of 1 in the last digit is allowed
    if name is None or number is None:
        return False
    if name.strip().lower() != str(question["answer"]).lower():
        return False
    decimals = question["decimals"]
    rounded = round(number, decimals)
    one_step = 10 ** (-decimals)
    return abs(rounded - question["value"]) <= one_step + 1e-9


def cost(input_tokens, output_tokens):
    return input_tokens / 1000000 * PRICE_INPUT + output_tokens / 1000000 * PRICE_OUTPUT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="1", help="run number, for example 1 or 2")
    parser.add_argument("--strategies", nargs="+", default=["S1", "S2", "S3"])
    parser.add_argument("--questions", nargs="*", default=None, help="for example Q-01 Q-09 (default: all 20)")
    args = parser.parse_args()

    with open("data/questions.json", encoding="utf-8") as f:
        questions = json.load(f)
    if args.questions:
        questions = [q for q in questions if q["id"] in args.questions]

    folder = os.path.join("outputs", "run" + args.run)
    log_folder = os.path.join(folder, "logs")
    os.makedirs(log_folder, exist_ok=True)

    summary = {}
    per_question = {}

    for strategy in args.strategies:
        function = STRATEGIES[strategy]
        results = []
        print("=== " + strategy + " ===")
        for q in questions:
            try:
                # only the question text goes to the model, never the correct answer
                r = function(q["question"], q["id"], log_folder=log_folder)
            except Exception as e:
                # an API error must not stop the whole run; the question counts as unanswered
                r = {"question_id": q["id"], "answer_name": None, "answer_number": None, "unanswered": True,
                     "input_tokens": 0, "output_tokens": 0, "seconds": 0, "error": str(e)[:300]}
            r["correct"] = is_correct(q, r["answer_name"], r["answer_number"])
            r["expected"] = str(q["answer"]) + " | " + str(q["value"])
            results.append(r)
            per_question.setdefault(q["id"], {})[strategy] = r["correct"]
            mark = "OK " if r["correct"] else "BAD"
            print(mark, q["id"], "->", r["answer_name"], "|", r["answer_number"],
                  " expected", r["expected"], " ", r["seconds"], "s")

        with open(os.path.join(folder, strategy + "_results.json"), "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        input_tokens = sum(r["input_tokens"] for r in results)
        output_tokens = sum(r["output_tokens"] for r in results)
        seconds = [r["seconds"] for r in results]
        summary[strategy] = {
            "correct": sum(1 for r in results if r["correct"]),
            "questions": len(results),
            "unanswered": sum(1 for r in results if r["unanswered"]),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "median_seconds": round(statistics.median(seconds), 2),
            "total_seconds": round(sum(seconds), 1),
            "cost": round(cost(input_tokens, output_tokens), 4),
        }

    # save the summary as JSON and as markdown tables for SUBMISSION.md
    with open(os.path.join(folder, "summary.json"), "w", encoding="utf-8") as f:
        json.dump({"model": MODEL, "k": K_SAMPLES, "time": time.ctime(), "summary": summary,
                   "per_question": per_question}, f, indent=2)

    names = {"S1": "S1 direct", "S2": "S2 think and vote (k = " + str(K_SAMPLES) + ")", "S3": "S3 tools"}
    lines = ["| Run | Strategy | Correct /" + str(len(questions)) + " | Unanswered | Input tokens | Output tokens"
             " | Median seconds per question | Total seconds | Cost ($) |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for strategy in summary:
        s = summary[strategy]
        lines.append("| " + args.run + " | " + names[strategy] + " | " + str(s["correct"]) + " | " + str(s["unanswered"])
                     + " | " + str(s["input_tokens"]) + " | " + str(s["output_tokens"]) + " | " + str(s["median_seconds"])
                     + " | " + str(s["total_seconds"]) + " | " + str(s["cost"]) + " |")
    lines.append("")
    lines.append("| Question | " + " | ".join(args.strategies) + " |")
    lines.append("|---|" + ":---:|" * len(args.strategies))
    for qid in per_question:
        marks = ["✓" if per_question[qid].get(s) else "✗" for s in args.strategies]
        lines.append("| " + qid + " | " + " | ".join(marks) + " |")

    table = "\n".join(lines)
    with open(os.path.join(folder, "summary.md"), "w", encoding="utf-8") as f:
        f.write(table + "\n")
    print()
    print(table)


if __name__ == "__main__":
    main()