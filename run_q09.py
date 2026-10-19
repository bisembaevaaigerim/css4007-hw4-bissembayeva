import json

from strategies import s3_tools

with open("data/questions.json", encoding="utf-8") as f:
    questions = json.load(f)

for q in questions:
    if q["id"] == "Q-09":
        result = s3_tools(q["question"], q["id"])
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("log saved to outputs/logs/S3_Q-09.json")