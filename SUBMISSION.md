# HW4 — submission

**AI assistance:** <!-- what you used, and for what. "None" is an answer too. -->

---

## Part A — Plan on paper (Easy)

> Commit this whole part before any `.py` file exists.

### A1 — The steps

I use this question as an example: *"Which district is denser, Brightwater or Millbrook, and by how much?"*

Steps 3-7 are inside my `lookup` tool. One `lookup` call = one fact.
Step 8 is my `calculate` tool.
In S3 the model does not see the documents and it does not do the maths by itself.

| # | Step | What goes in (types) | What comes out (types) | When it goes wrong | Tool, loop, or model? |
|---|---|---|---|---|---|
| 1 | Understand the question | `question: str` | `districts: list[str]` (for example `["Brightwater","Millbrook"]`), `quantity: str` (for example `"population density 2025"`), `answer_kind: str` (`"which + difference"`, `"yes/no + difference"` or `"projection"`) | If the question has a district that does not exist, the model still sends it to `lookup` and step 3 gives an error | model |
| 2 | Choose fields and formula | `quantity: str` | `fields: list[str]` from my list in A2 (for example `["population_2025","area_km2"]`), `formula: str` (for example `"population_2025 / area_km2"`) | If we do not have the data (for example income), the model says it can not answer from the documents | model |
| 3 | Check the district name | `name: str` | `district: str` (one of the 12 names) | If there is no exact match (I ignore big/small letters) it returns an error with max 2 close names, like `"no district named Ossbrige; did you mean Ossbridge or Ossford?"`. I do not fix the name automatically because Ossbridge and Ossford are too similar. Empty name gives an error too | tool (`lookup`) |
| 4 | Choose the current profile | `district: str` | `doc_id: str` (for example `"NR-05"`) | I skip profiles with `ARCHIVED` in the title. If there is no current profile: error `"no current profile"`. If there are 2 current profiles: error `"conflicting profiles"`, it does not choose one | tool (`lookup`) |
| 5 | Read the number from the profile | `doc_text: str`, `field: str` | `value: float`, `unit: str`, `evidence: str` (the sentence where the number is) | Unknown field: error with the list of fields I allow. Field is not in the text: error `"field not found in NR-xx"`. Number can not be read: error, no guessing. The documents write numbers like `"1,284.6"`, so I need to remove the comma and get `1284.6` | tool (`lookup`) |
| 6 | Use corrections | `district: str`, `field: str`, `value: float`, correction notices `list[doc]` | `value: float` (new one if it was corrected), `corrected_by: str \| None` (for example `"NR-16"`) | If a notice is about this district and field but I can not read its number, I return an error. I think no answer is better than a wrong answer | tool (`lookup`) |
| 7 | Use one unit | `value: float`, `unit: str` | `value: float` in my standard unit (water in megalitres, area in km2, budget in million tenge), `note: str` (for example `"changed from 2151400 cubic metres"`) | Unknown unit: error `"unknown unit"` | tool (`lookup`) |
| 8 | Calculate | `expression: str` (for example `"44675 / 921.4"`) | `result: float` | Wrong syntax, things I do not allow (names, function calls, attributes), division by zero, or too big number: it returns an error and does not run anything | tool (`calculate`) |
| 9 | Compare | 2 or 3 pairs `(district: str, value: float)` | `winner: str` (or `"yes"` / `"no"`), `difference: float` (always positive) | If the values are the same, the model says it is a tie | model |
| 10 | Write the final answer | `winner: str`, `difference: float` | the last line is `ANSWER: <name or yes/no> \| <number>`, number with 3 decimals | If the model forgets this line or the round limit is reached, the loop marks the question as unanswered | model |
| L | Run the conversation | `messages: list[dict]`, model reply with `tool_calls` | one `role: "tool"` message for every `tool_call_id`, and the final text | If `arguments` is not valid JSON or a needed key is missing, I send an error back to the model and do not run the tool. Unknown tool name: error. Too many rounds: stop and mark unanswered | loop |

**How the steps connect:**

1. The question goes to step 1.
2. Step 1 gives the district names and what we need to compare. This goes to step 2.
3. Step 2 gives the fields and the formula. Then the model calls `lookup` for every district and every field.
4. Inside `lookup` the steps go 3 -> 4 -> 5 -> 6 -> 7:
   - step 3 gives the correct name to step 4
   - step 4 gives the profile to step 5
   - step 5 gives the raw number to step 6
   - step 6 gives the corrected number to step 7
   - step 7 gives the final number back to the model together with the document id
5. The model puts the numbers into the formula and sends it to step 8 (`calculate`).
6. Step 8 gives the results to step 9.
7. Step 9 gives the winner and the difference to step 10.
8. Step 10 writes the last line `ANSWER: ... | ...`.
9. The loop (L) works between all steps. It takes the requests from the model (steps 1, 2, 9, 10) to the tools (steps 3-8) and brings the results back.

**What I am assuming:**

- Year: "2025" numbers are from the 2025 profiles. Population is from the 2025 census, budget is for 2025, water is household use in 2025, pupils are for 2025/26 (NR-00 says this). I use the 2020 population only for growth questions.
- Archived profiles (NR-13 and NR-14) are never used. They are from 2019 and NR-00 says they are old.
- Corrections are more important than the profile (NR-00 says this). There is one correction: NR-16 changes Brightwater area from 912.4 to 921.4 km2.
- Units: I compare water in megalitres. 1 megalitre = 1000 m3 (NR-15), so Lindenmoor 2151400 m3 = 2151.4 ML. 1 ML = 1000000 litres. "Per day" means I divide by 365 days (2025 is not a leap year).
- Water price: the 2025 price is 142.35 tenge per m3 and it is the same in all districts (NR-15).
- Formulas: density = population / area, growth % = (new - old) / old * 100. Difference is always positive.
- I round only one time, at the end. Numbers in the middle are not rounded. The model writes 3 decimals and the checker rounds to the `decimals` from the question.
- My most important assumption: `lookup` must take the right number for the right field. The profiles use 3 different sentence styles (NR-01/04/07/10, NR-02/05/08/11, NR-03/06/09/12). Also many sentences have 2 similar numbers, like the 2020 and 2025 population. If step 5 takes the wrong one, all other steps still work but the answer is wrong and there is no error. Because of this step 5 returns the `evidence` sentence and I will write the most tests for it.


### A2 — The two tools

I decided that `lookup` takes one district and one field and gives back one number.
I did not choose a search tool that returns sentences, because then the model must find
the archived profiles, the correction and the units by itself, and this is where it makes mistakes.
With my design all traps are handled inside the tool and the model gets a clean number with its source.

#### `lookup`

```json
{
  "type": "function",
  "function": {
    "name": "lookup",
    "description": "Get ONE fact about ONE district of the Nine Rivers Region from the official 2025 profiles. Call it once for every number you need (for example, 2 districts x 2 fields = 4 calls). The 12 districts are: Ossbridge, Ossford, Tarnvale, Kelmarsh, Brightwater, Stonecairn, Harrowfield, Lindenmoor, Redfen, Ashgrove, Millbrook, Coldharbour. Be careful: Ossbridge and Ossford are different districts. The tool already skips old ARCHIVED profiles, applies correction notices and converts units, so the value you get is the one to use. Water use is always in megalitres. For the water price use district \"Region\" and field \"water_tariff_2025\". The result has the value, the unit, the source document id and the sentence the value came from. If the result has an \"error\" key, read it, fix your input and try again. Do not do maths yourself, use the calculate tool.",
    "parameters": {
      "type": "object",
      "properties": {
        "district": {
          "type": "string",
          "description": "Exact district name, for example \"Brightwater\". Use \"Region\" only for water_tariff_2025."
        },
        "field": {
          "type": "string",
          "enum": [
            "population_2025",
            "population_2020",
            "area_km2",
            "budget_2025_million_tenge",
            "water_use_2025_megalitres",
            "schools",
            "pupils_2025_26",
            "paved_road_km",
            "founded_year",
            "water_tariff_2025"
          ],
          "description": "Which fact you need."
        }
      },
      "required": ["district", "field"],
      "additionalProperties": false
    }
  }
}
```

| Case | What the tool returns |
|---|---|
| success | `{"district": "Brightwater", "field": "area_km2", "value": 921.4, "unit": "km2", "source": "NR-05", "corrected_by": "NR-16", "note": "NR-16 corrects 912.4 to 921.4", "evidence": "The district, founded in 1889, stretches along the Bright over 912.4 square kilometres and keeps 455.0 km of paved road."}` |
| success with unit change (Lindenmoor water) | `{..., "value": 2151.4, "unit": "megalitres", "source": "NR-08", "corrected_by": null, "note": "changed from 2151400 cubic metres", ...}` |
| district with a typo (`"Ossbrige"`) | `{"error": "no district named Ossbrige; did you mean Ossbridge or Ossford?"}` |
| name that fits 2 districts (`"Oss"`) | `{"error": "Oss is not a full district name; did you mean Ossbridge or Ossford?"}` |
| empty district or district longer than 50 characters | `{"error": "district must be a district name, for example Brightwater"}` |
| field not in the list | `{"error": "unknown field density; allowed fields are: population_2025, population_2020, ..."}` |
| district has only archived profiles | `{"error": "no current profile for X; archived profiles are not used"}` (does not happen in our data, Tarnvale and Kelmarsh also have 2025 profiles, so the tool returns NR-03 and NR-04, never NR-13 or NR-14) |
| field not found in the profile text | `{"error": "field schools not found in NR-xx"}` |
| `"Region"` used with a field that is not the tariff | `{"error": "Region can only be used with water_tariff_2025"}` |
| unknown unit | `{"error": "unknown unit for water_use_2025_megalitres in NR-xx"}` |

**Worst thing it could do with strange or dangerous input:**
If my pattern for a field is wrong, lookup can return a wrong number (for example the 2020 population instead of 2025) with no error. The model will trust it and the answer will be wrong. This is why the result has the evidence sentence and why I test step 5 the most.

#### `calculate`

```json
{
  "type": "function",
  "function": {
    "name": "calculate",
    "description": "Calculate an arithmetic expression exactly. Use it for EVERY calculation (divisions, differences, percentages, unit changes), never do maths in your head. Only numbers, + - * / ** and brackets are allowed, for example \"(52904 - 48317) / 48317 * 100\". Do not use commas inside numbers (write 1284.6, not 1,284.6). No variables, no functions, no text. The result is a number with full precision, do not round it before the final answer. If the result has an \"error\" key, fix the expression and try again.",
    "parameters": {
      "type": "object",
      "properties": {
        "expression": {
          "type": "string",
          "description": "Arithmetic expression, for example \"44675 / 921.4\"."
        }
      },
      "required": ["expression"],
      "additionalProperties": false
    }
  }
}
```

| Case | What the tool returns |
|---|---|
| success | `{"expression": "44675 / 921.4", "result": 48.48599956587801}` |
| empty expression or longer than 200 characters | `{"error": "expression must be 1 to 200 characters"}` |
| wrong syntax (`"44675 //// 9"`) | `{"error": "invalid syntax"}` |
| something that is not allowed: names, function calls, attributes, strings (`"__import__('os').system('echo hi')"`, `"(1).__class__"`) | `{"error": "not allowed: only numbers, + - * / ** and brackets"}` (nothing is run, the expression is only read with `ast.parse`) |
| division by zero | `{"error": "division by zero"}` |
| too big power (`"9**9**9"`) | `{"error": "number too large: exponent must be between -10 and 10"}` (checked before the power is calculated, so it does not freeze) |
| result too big | `{"error": "number too large: result is bigger than 1e15"}` |
| too many brackets inside each other | `{"error": "expression too complex"}` |

**Worst thing it could do with strange or dangerous input:**
If I used `eval`, the model could run any Python code on my computer, for example delete files with `__import__('os')`. My `calculate` does not use `eval`. It reads the expression with `ast.parse` and only accepts numbers, the operators `+ - * / **` and brackets. Everything else is rejected before anything is calculated. The worst thing that is still possible is a very slow calculation like `9**9**9`, which can freeze the program. I block it by checking the exponent before I calculate it, by limiting the result size and by limiting the length of the expression. The model can still send a wrong formula, but then the tool gives the correct result of a wrong formula. It can not fix the model's logic.

### A3 — Q-09 by hand

Q-09: *"Which district has the higher population density in 2025, Brightwater or Millbrook, and by how many residents per square kilometre?"*

I expect 3 calls to the model:
- round 1: the model asks for 4 facts at the same time (2 districts x 2 fields)
- round 2: the model asks for 3 calculations at the same time
- round 3: the model writes the final answer

So it is 3 model calls and 7 tool calls. I calculate the difference in one expression from the raw numbers, so nothing is rounded in the middle.
Note: `arguments` is a string with JSON inside, this is how the API sends it.
The `evidence` is copied from the documents, so the numbers there have commas like in the original text.

```json
[
  {
    "role": "system",
    "content": "Answer questions about the Nine Rivers Region. You do not have the documents. Get every fact with the lookup tool and do every calculation with the calculate tool. End your reply with one line: ANSWER: <name or yes/no> | <number with 3 decimals>"
  },
  {
    "role": "user",
    "content": "Which district has the higher population density in 2025, Brightwater or Millbrook, and by how many residents per square kilometre?"
  },

  {
    "role": "assistant",
    "content": null,
    "tool_calls": [
      {"id": "call_1", "type": "function", "function": {"name": "lookup", "arguments": "{\"district\": \"Brightwater\", \"field\": \"population_2025\"}"}},
      {"id": "call_2", "type": "function", "function": {"name": "lookup", "arguments": "{\"district\": \"Brightwater\", \"field\": \"area_km2\"}"}},
      {"id": "call_3", "type": "function", "function": {"name": "lookup", "arguments": "{\"district\": \"Millbrook\", \"field\": \"population_2025\"}"}},
      {"id": "call_4", "type": "function", "function": {"name": "lookup", "arguments": "{\"district\": \"Millbrook\", \"field\": \"area_km2\"}"}}
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_1",
    "content": "{\"district\": \"Brightwater\", \"field\": \"population_2025\", \"value\": 44675, \"unit\": \"residents\", \"source\": \"NR-05\", \"corrected_by\": null, \"note\": \"\", \"evidence\": \"Census population: 39,902 in 2020 and 44,675 in 2025.\"}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_2",
    "content": "{\"district\": \"Brightwater\", \"field\": \"area_km2\", \"value\": 921.4, \"unit\": \"km2\", \"source\": \"NR-05\", \"corrected_by\": \"NR-16\", \"note\": \"NR-16 corrects 912.4 to 921.4\", \"evidence\": \"The district, founded in 1889, stretches along the Bright over 912.4 square kilometres and keeps 455.0 km of paved road.\"}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_3",
    "content": "{\"district\": \"Millbrook\", \"field\": \"population_2025\", \"value\": 37203, \"unit\": \"residents\", \"source\": \"NR-11\", \"corrected_by\": null, \"note\": \"\", \"evidence\": \"Census population: 34,590 in 2020 and 37,203 in 2025.\"}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_4",
    "content": "{\"district\": \"Millbrook\", \"field\": \"area_km2\", \"value\": 758.6, \"unit\": \"km2\", \"source\": \"NR-11\", \"corrected_by\": null, \"note\": \"\", \"evidence\": \"The district, founded in 1897, stretches along the Mill Brook over 758.6 square kilometres and keeps 360.1 km of paved road.\"}"
  },

  {
    "role": "assistant",
    "content": null,
    "tool_calls": [
      {"id": "call_5", "type": "function", "function": {"name": "calculate", "arguments": "{\"expression\": \"44675 / 921.4\"}"}},
      {"id": "call_6", "type": "function", "function": {"name": "calculate", "arguments": "{\"expression\": \"37203 / 758.6\"}"}},
      {"id": "call_7", "type": "function", "function": {"name": "calculate", "arguments": "{\"expression\": \"37203 / 758.6 - 44675 / 921.4\"}"}}
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_5",
    "content": "{\"expression\": \"44675 / 921.4\", \"result\": 48.48599956587801}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_6",
    "content": "{\"expression\": \"37203 / 758.6\", \"result\": 49.041655681518584}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_7",
    "content": "{\"expression\": \"37203 / 758.6 - 44675 / 921.4\", \"result\": 0.5556561156405735}"
  },

  {
    "role": "assistant",
    "content": "Brightwater has 48.486 residents per km2 (44675 residents on 921.4 km2, the area is corrected by NR-16). Millbrook has 49.042 residents per km2 (37203 residents on 758.6 km2). Millbrook is denser by 0.556 residents per km2.\nANSWER: Millbrook | 0.556"
  }
]
```

**My arithmetic:**

- Brightwater = 48.4860 residents per km2
- Millbrook = 49.0417 residents per km2

Millbrook is bigger, so Millbrook is denser.
Difference = 0.5557 = **0.6**.
This is the same as the correct answer in `questions.json` (Millbrook, 0.6), so the conversation gives the right answer.

Why the traps matter here:
- If the model used the wrong area 912.4 from NR-05: 44675 / 912.4 = 48.9643, difference = 49.0417 - 48.9643 = 0.0774, rounded = **0.1**. Wrong answer, but Millbrook is still the winner, so only the number would be wrong and it would be easy to miss.
- If the densities were rounded before the subtraction: 49.0 - 48.5 = **0.5**. Also wrong. This is why I round only at the end.

### A4 — Why I split it this way

**Other way: a search `lookup`.** `lookup` returns 2-3 sentences that match a phrase like `"Brightwater area"`, and the model takes the number by itself.

Good points: it is more flexible (the model can ask about anything, not only my 10 fields) and the tool is simpler to write.

**Why I did not choose it:**
1. **The traps move to the model.** The model must notice ARCHIVED profiles (NR-13, NR-14), search for the correction NR-16 by itself and convert Lindenmoor cubic metres. These are the traps where a model makes mistakes. In my design these rules are in code and work the same every time.
2. **Easier to test.** I can test "Brightwater area_km2 gives 921.4 from NR-05, corrected by NR-16" without the model. With search, the important part (does the model choose the right number?) can only be checked by running the model.
3. **Fewer tokens.** My tool returns one number and one sentence, not 2-3 sentences. Every tool result stays in the conversation, so it is sent again in every next round.
4. **No wrong number from the right sentence.** NR-05 says "39,902 in 2020 and 44,675 in 2025" in one sentence. The model could take the wrong one, my tool takes the 2025 number in code.


---

## Part B — Build it and run it (Medium)

### What I changed from Part A while coding

<!-- what changed in your plan, and why. "None" is an answer too. -->

### B2 — Tests

```text
tests/test_tools.py::test_calculate_multiplication PASSED                                                                                                  [  5%]
tests/test_tools.py::test_calculate_q09_difference PASSED                                                                                                  [ 10%]
tests/test_tools.py::test_calculate_refuses_import PASSED                                                                                                  [ 15%]
tests/test_tools.py::test_calculate_refuses_class PASSED                                                                                                   [ 21%]
tests/test_tools.py::test_calculate_refuses_huge_power_fast PASSED                                                                                         [ 26%]
tests/test_tools.py::test_calculate_refuses_other_huge_powers PASSED                                                                                       [ 31%]
tests/test_tools.py::test_calculate_division_by_zero PASSED                                                                                                [ 36%]
tests/test_tools.py::test_calculate_refuses_functions_and_text PASSED                                                                                      [ 42%]
tests/test_tools.py::test_calculate_bad_input_does_not_crash PASSED                                                                                        [ 47%]
tests/test_tools.py::test_lookup_finds_2025_population PASSED                                                                                              [ 52%]
tests/test_tools.py::test_lookup_takes_2025_not_2020 PASSED                                                                                                [ 57%]
tests/test_tools.py::test_lookup_uses_correction PASSED                                                                                                    [ 63%]
tests/test_tools.py::test_lookup_skips_archived_profile PASSED                                                                                             [ 68%]
tests/test_tools.py::test_lookup_misspelled_name PASSED                                                                                                    [ 73%]
tests/test_tools.py::test_lookup_similar_names_are_different PASSED                                                                                        [ 78%]
tests/test_tools.py::test_lookup_part_of_name_is_not_guessed PASSED                                                                                        [ 84%]
tests/test_tools.py::test_lookup_converts_cubic_metres PASSED                                                                                              [ 89%]
tests/test_tools.py::test_lookup_water_tariff PASSED                                                                                                       [ 94%]
tests/test_tools.py::test_lookup_bad_input_does_not_crash PASSED                                                                                           [100%]

====================================================================== 19 passed in 0.15s =======================================================================
```

### B3 — The loop

- Round limit, and why: 8 rounds. A normal question needs about 3-4 rounds (facts, then maths, then the answer). Questions with 3 districts (Q-11, Q-13, Q-20) can need 1 more round, and I leave space for 1-2 retries after an error (for example a wrong district name). If the model needs more than 8 rounds it is probably stuck in a loop. Also every round costs more than the one before, because the whole conversation is sent again. If the limit is reached, the question is marked as unanswered.
- Where the logs are: `outputs/logs/S3_<question id>.json`. Every log has every round with its input and output tokens, every tool call (id, tool, arguments, result, seconds) and the full message list.
- Real Q-09 conversation compared with my A3 version, what is different:
  - Round 1 is the same as my plan: 4 `lookup` calls at the same time with the same districts and fields. `lookup` returned Brightwater area 921.4 with `corrected_by: NR-16`, so the trap worked as planned.
  - I expected 3 model calls, the real run used 4. I planned 3 `calculate` calls in one round. The model first asked for the 2 densities, and only after it saw them it asked for the difference in a new round. So the model works step by step and looks at the results before it plans the next step.
  - The number of tool calls is the same (7), and the answer is the same: `Millbrook | 0.556` (0.6 after rounding, correct).
  - Input tokens grew every round: 748, 1212, 1331, 1406. The extra round cost 1406 more input tokens.

### B4 — Three strategies

**What I kept the same:**

- Model: `gpt-5.6-luna` for all calls, Chat Completions API.
- `reasoning_effort="none"` for all 3 strategies (the model can not use tools in Chat Completions with hidden reasoning, so I switched it off everywhere to keep it fair).
- The same 20 questions from `data/questions.json`. Only the question text goes to the model, never the correct answer.
- The same answer format for all strategies: the last line `ANSWER: <name or yes/no> | <number>`, number with 3 decimals. One function (`find_answer`) reads it and one function (`is_correct`) checks it.
- S1 and S2 get exactly the same system message (answer rule + all 17 documents). The only difference: S2 adds one line to the question ("Think step by step...") and asks 5 times.
- S2: k = 5, `temperature = 1.0` (the model allows it, I checked it in the test run, the field `temperature` in `S2_results.json` is 1.0). S1 and S3 use the default temperature.
- S3 gets no documents, only the two tools from A2, and the same answer rule. Round limit 8.
- Tokens are counted from `usage` of every call: 1 call in S1, all 5 calls in S2, every round in S3.
- Time is measured from the first call to the last call of each question. Calls run one after another, not in parallel.
- Price: $0.20 per 1M input tokens and $1.20 per 1M output tokens.
- I ran everything 2 times (run 1 and run 2) with the same code and settings.

<!-- model, temperature, k, prompts, answer format, anything else -->

**My rule for a correct answer** (written before the first full run):
- The model must end with the line `ANSWER: <name or yes/no> | <number>`. My code takes the last such line. If there is no such line, the question is unanswered (and wrong).
- The name must be the same as `answer` (big/small letters do not matter).
- The number is rounded to the question's `decimals` and must be equal to `value`; a difference of 1 in the last digit is allowed (for example for Q-09, `decimals` = 1, so 0.5, 0.6 and 0.7 are counted as correct).
- For S2 I first take the most common (name, number) pair of the 5 answers and then check it with the same rule.

| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 direct | 10 | 5 | 43900 | 887 | 1.54 | 30.8 | 0.0098 |
| 1 | S2 think and vote (k = 5) | 15 | 0 | 222100 | 18664 | 11.15 | 223.9 | 0.0668 |
| 1 | S3 tools | 20 | 0 | 88354 | 4763 | 5.84 | 114.3 | 0.0234 |
| 2 | S1 direct | 10 | 4 | 43900 | 927 | 1.37 | 28.0 | 0.0099 |
| 2 | S2 think and vote (k = 5) | 17 | 0 | 222100 | 18756 | 10.97 | 223.8 | 0.0669 |
| 2 | S3 tools | 20 | 0 | 88122 | 4671 | 5.2 | 100.3 | 0.0232 |

Cost is calculated with $0.20 per 1M input tokens and $1.20 per 1M output tokens.
One full run (all 3 strategies, 20 questions) cost about $0.10, so the 2 full runs cost about $0.20. The test run on 3 questions and the Q-09 test cost about $0.02 more.

**Per question (run 1):**

| Question | S1 | S2 | S3 |
|---|:---:|:---:|:---:|
| Q-01 | ✓ | ✓ | ✓ |
| Q-02 | ✗ | ✓ | ✓ |
| Q-03 | ✗ | ✓ | ✓ |
| Q-04 | ✓ | ✓ | ✓ |
| Q-05 | ✗ | ✗ | ✓ |
| Q-06 | ✓ | ✓ | ✓ |
| Q-07 | ✓ | ✓ | ✓ |
| Q-08 | ✗ | ✗ | ✓ |
| Q-09 | ✗ | ✓ | ✓ |
| Q-10 | ✓ | ✓ | ✓ |
| Q-11 | ✗ | ✓ | ✓ |
| Q-12 | ✗ | ✗ | ✓ |
| Q-13 | ✓ | ✓ | ✓ |
| Q-14 | ✓ | ✓ | ✓ |
| Q-15 | ✗ | ✓ | ✓ |
| Q-16 | ✓ | ✓ | ✓ |
| Q-17 | ✗ | ✗ | ✓ |
| Q-18 | ✓ | ✓ | ✓ |
| Q-19 | ✓ | ✓ | ✓ |
| Q-20 | ✗ | ✗ | ✓ |

Full tables for both runs are in `outputs/run1/summary.md` and `outputs/run2/summary.md`.

---

## Part C — Explain and choose (Hard)

### C1 — Does the tool description matter?

I ran S3 again on 5 questions: Q-01 (Ossbridge/Ossford), Q-03 (Lindenmoor cubic metres), Q-08 (water price), Q-09 (correction NR-16) and Q-17 (water price per resident). I chose them because my `lookup` description gives a hint for each of them. I ran both versions at the same time (`run_c1.py`, logs in `outputs/c1/logs/`). In the vague version only the `lookup` description is changed to `"Looks things up."`, the parameters and the `calculate` tool are the same.

| Question | Calls (your description) | Calls (vague) | Answer (yours) | Answer (vague) |
|---|---:|---:|---|---|
| Q-01 | 7 tool calls, 4 model calls | 7 tool calls, 4 model calls | Ossbridge \| 4.57 ✓ | Ossbridge \| 4.57 ✓ |
| Q-03 | 7 tool calls, 4 model calls | 5 tool calls, 3 model calls | Lindenmoor \| 5.34 ✓ | Lindenmoor \| 5.34 ✓ |
| Q-08 | 4 tool calls, 3 model calls | 4 tool calls, 3 model calls | Brightwater \| 72.456 ✓ | Brightwater \| 72.456 ✓ |
| Q-09 | 7 tool calls, 4 model calls | 7 tool calls, 4 model calls | Millbrook \| 0.556 ✓ | Millbrook \| 0.556 ✓ |
| Q-17 | 8 tool calls, 4 model calls | 6 tool calls, 3 model calls | Harrowfield \| 884.457 ✓ | Harrowfield \| 884.457 ✓ |

**What changed:**
- The answers did not change, all 10 are correct, and no tool returned an error.
- The inputs to `lookup` were exactly the same in both versions, for all 5 questions. Even for Q-08 the vague version asked `{"district": "Region", "field": "water_tariff_2025"}` at once.
- The vague version used fewer input tokens every time. For Q-01 and Q-09 the number of model calls was the same (4), and the difference was 960 tokens, so my long description costs about 240 tokens in every model call.
- For Q-03 and Q-17 the vague version needed 1 round and 2 `calculate` calls less (it wrote the formula in fewer steps). With only one run I can not say if this is because of the description or just random.

**Why:**
Before the run I expected that with the vague description the model would not know how to ask for the water price (Q-08, Q-17) and would make wrong calls. This did not happen. The reason is that the task said to change only the description, and a lot of information is also in the parameters:
- the `district` parameter has its own description that says to use `"Region"` for `water_tariff_2025`;
- the `field` parameter is an `enum`, so the model sees the exact list of facts and their units (`water_use_2025_megalitres`, `water_tariff_2025`).
Also my `lookup` handles the traps (archived profiles, NR-16, cubic metres) in code, so the model does not need to know about them. The text about the traps in my description was information, not something the model needs to get the right answer.

So in my design the description matters less than I thought, because the parameter schema already explains how to use the tool. The description still has a cost: about 240 tokens in every S3 request. I think the description would matter much more if `field` was a free string without `enum`, or if `lookup` did not handle the traps by itself.

### C2 — Three mistakes explained

#### S1 (direct): Q-02, run 1

Log `outputs/run1/S1_results.json`, Q-02:
> "Harrowfield grew faster by 0.226 percentage points. Tarnvale grew 6.209% and Harrowfield grew 7.211%. ANSWER: Harrowfield | 0.226"

The correct answer is Harrowfield, 1.69. The correct growth is Tarnvale (71388 - 67214) / 67214 = 6.210% and Harrowfield (90212 - 83609) / 83609 = 7.897%.

What happened: the name is right, but the maths is wrong twice. First, the Harrowfield growth (7.211%) is wrong. Second, the model can not even subtract its own numbers: 7.211 - 6.209 = 1.002, but it wrote 0.226. In S1 there is no place for steps: the model wrote one short answer, so it has to find 4 numbers, do 2 divisions and 1 subtraction "in one jump". A language model makes the next token from the text it already has, so when the middle results are not written down, it has nothing to build on, and the numbers it writes are only "probable looking" numbers. This is also why 5 S1 answers had no `ANSWER:` line at all: for example Q-09 was only `Millbrook | 0.000` with 10 output tokens. Even if my parser read those lines, 4 of the 5 numbers were also wrong (Q-17: 8.807 instead of 884, Q-20: Harrowfield instead of Ashgrove), so the format rule changed the score by at most 1 question (Q-15).

#### S2 (think and vote): Q-17, run 1

Log `outputs/run1/logs/S2_Q-17.json`, all 5 answers and sample 1:
> all 5 answers: Harrowfield | 886.395, 890.122, 887.578, 887.601, 885.665, votes: 1 of 5
> "Harrowfield: 7,146 × 1,000 × 142.35 ÷ 90,212 = 11,278.289 tenge per resident. Ossbridge: 3,862 × 1,000 × 142.35 ÷ 52,904 = 10,391.894 ... Difference: 886.395"

The correct answer is Harrowfield, 884 (exact 884.457).

What happened: step-by-step thinking fixed the facts. All facts and their documents are right (NR-07, NR-01, NR-15), the unit change from megalitres to cubic metres is right and the formula is right. Only the division is wrong: 1017233100 / 90212 is 11276.029, not 11278.289 (+2.26 tenge). So writing the steps helps with the logic, but the model still does the long division "in its head".

Why voting did not fix it: voting works when wrong answers are different and the right answer repeats, like a name (Millbrook or Brightwater) or yes/no. Here the answer is a number with 3 decimals. Every sample made a slightly different arithmetic mistake, so all 5 numbers are different and every answer got 1 vote. My code then takes the first one, so voting did nothing. The same happened in Q-05, Q-12 and Q-20 (all "1 of 5"). Even the average of the 5 numbers would not help: all 5 are bigger than 884.457 (885.7 to 890.1), so the error is a bias, not random noise. Taking k samples reduces the random part of the error (variance), but it can not remove an error that goes in the same direction every time (bias).

Voting can even make a mistake stronger. In Q-08 the 5 answers were `yes | 72.156`, `Brightwater | 72.456`, `yes | 72.456`, `Brightwater | 72.036`, `yes | 72.456`. The model often answered "yes" instead of the district name (my answer rule says "<district name or yes/no>", and the question "whose households paid more" confused it). `yes | 72.456` appeared 2 times and won the vote, so the common format mistake beat the correct answer.

Price: S2 used 5 calls per question and long reasoning, so it cost $0.0668 in run 1, almost 7 times more than S1 ($0.0098), and still had 5 wrong answers.

#### S3 (tools): no mistakes, so the most expensive question: Q-20, run 1

S3 was correct on all 20 questions in both runs. The most expensive question was Q-20 (5504 input tokens, 335 output tokens, 4 model calls, 10 tool calls). Log `outputs/run1/logs/S3_Q-20.json`:

| Round | Input tokens | What the model asked for |
|---|---:|---|
| 1 | 761 | 6 × `lookup`: budget and population for Ossbridge, Ashgrove, Harrowfield |
| 2 | 1424 | 3 × `calculate`: `9284.5 * 1000000 / 52904`, `10488.1 * 1000000 / 58760`, `16021.7 * 1000000 / 90212` |
| 3 | 1622 | 1 × `calculate`: `178490.46970728386 - 175497.12687131407` |
| 4 | 1697 | final answer `Ashgrove | 2993.343` (correct: 2993) |

Why it needed this many rounds: Q-20 has 3 districts, so it needs 6 facts. The facts come in round 1, the 3 divisions can only be written after the facts are known (round 2), and the difference "highest minus lowest" can only be written after the model sees which result is the highest and which is the lowest (round 3). Each step depends on the result of the step before, so they can not be in the same round. Then one more call for the answer.

Why each round costs more: the model does not remember anything between calls, so every round sends the whole conversation again: the system message, the tool definitions, the question and all old tool calls and results. Round 2 is +663 tokens because the 6 `lookup` results (with their `evidence` sentences) are now in the conversation. Rounds 3 and 4 add less, because `calculate` results are short. So the total (5504) is much more than the last round alone (1697).

Why the calculator removes the mistakes from S1 and S2: `calculate` does the division in Python, so the result is exact every time (2993.343, and 884.457 for Q-17, where S2 had 886.395). The model only has to choose the right formula. In round 3 the model even copied the full numbers from the calculator results (`178490.46970728386`), so nothing was rounded in the middle. The error that S2 can not remove (the arithmetic bias) does not exist in S3 at all. The cost is more model calls per question (4 instead of 1) and more tokens than S1, but S3 was still about 3 times cheaper than S2 ($0.0234 vs $0.0668).

### C3 — Which strategy I would use, and what would change it

**My choice: S3 (tools).**

| | S1 direct | S2 think and vote | S3 tools |
|---|---|---|---|
| Correct (run 1 / run 2) | 10 / 10 | 15 / 17 | **20 / 20** |
| Cost for 20 questions | $0.0098 | $0.0668 | $0.0234 |
| Tokens (input + output, run 1) | 44787 | 240764 | 93117 |
| Median seconds per question | 1.5 | 11.1 | 5.8 |

S3 was the only strategy with no mistakes, and it gave the same answers in both runs. It is in the middle for cost and time: about 2.4 times more expensive than S1, but 2.9 times cheaper than S2, and 2 times faster than S2.

The reason is the principle, not only the number: in this task every question needs exact facts and exact arithmetic. S3 moves both parts out of the model. `lookup` handles the traps (archived profiles, the NR-16 correction, cubic metres) in code, and `calculate` does the maths exactly. The model only has to plan which facts to get and which formula to use, and this is the part it does well.

**Why not S1:** it is the cheapest and fastest, but it was wrong on half of the questions (10/20 in both runs). Without a place to write the steps the model guesses the numbers (Q-02: it wrote 0.226 although its own numbers give 1.002), sometimes even the winner is wrong (Q-12), and 4-5 times per run it did not follow the answer format. A cheap answer that is wrong half of the time is not useful.

**Why not S2:** writing the steps fixed most of the facts and the logic (15-17/20), but S2 is the most expensive (almost 7 times S1, 3 times S3) and the slowest (11 seconds per question). And it can not fix its main remaining problem: the long divisions in its head. Voting does not help here, because every sample makes a slightly different number (votes "1 of 5" in Q-05, Q-12, Q-17, Q-20), and the error goes in the same direction (Q-17: all 5 numbers above 884.457). Paying 5 times more for the same kind of mistake is not a good deal.

**Situations that would change my choice:**

1. **Questions with no arithmetic**, only one fact (for example "When was Stonecairn founded?"). Then the calculator is not needed and the traps are the only risk. I would pick **S1**, maybe with a short "think step by step": it is 1 call, about 1.5 seconds and the cheapest. Q-10 (founding years, only a subtraction of two years) was correct for all 3 strategies in both runs.
2. **A strict time limit**, for example an answer in under 2 seconds. S3 needs 3-4 calls one after another (median 5.8 s), S2 needs 11 s. Only **S1** fits, and I would accept the lower accuracy (or answer only the simple questions).
3. **1000 times more documents** (about 2.3 million tokens). S1 and S2 put all documents in the prompt, so this does not fit in the model's context at all, and even if it did, every S2 question would cost 1000 times more. **S3** becomes even better, because it never sends the documents, but my `lookup` would need an index (see final question 6).
4. **A very small budget.** S3 is still my choice, because it is only $0.0234 for 20 questions and correct. S2 is the first strategy I would drop. Only if the budget was so small that 3-4 calls per question are too many, I would use S1.
5. **Questions that my 10 fields can not answer** (for example "Which river is Ossbridge on?"). My `lookup` has no field for this. Then I would use **S2** or change `lookup` to a search tool that returns sentences.

### C4 — How sure I can be

**How different were my two runs?**
- S1: 10/20 in both runs, but this hides the noise: 4 questions changed (Q-02 and Q-09 became correct, Q-14 and Q-19 became wrong).
- S2: 15/20 and 17/20, 2 questions changed (Q-08 and Q-20 became correct).
- S3: 20/20 in both runs, no question changed, and the numbers were exactly the same (the calculator gives the same result every time).
So with 20 questions one strategy can move by 2-4 questions between two runs, only because of randomness.

**Is the difference between my two best strategies bigger than that?**
The two best are S3 and S2. The difference is 5 questions in run 1 (20 vs 15) and 3 in run 2 (20 vs 17). This is bigger than the S2 noise (2 questions), but not by much. A better way is to look at the questions where they disagree. On 5 questions (Q-05, Q-08, Q-12, Q-17, Q-20) S3 was better in at least one run, and there was no question where S2 was better than S3. If both strategies were equally good, each of these 5 questions would go either way like a coin, and the chance that all 5 go to S3 (or all 5 to S2) is 2 × (1/2)^5 = 0.0625, about 6%. So the result is strong, but with 20 questions it is just at the edge of what people normally accept (5%). Q-05, Q-12 and Q-17 were wrong for S2 in both runs, so these are not just bad luck.

The difference between S2/S3 and S1 (about 7-10 questions) is much bigger than the noise, so I trust that S1 is the worst.

**What 20 questions can not show:**
- S3 had 0 mistakes in 20, but this does not mean 100%. With 0 errors in 20 the real error rate can still be up to about 3/20 = 15% (the "rule of three", 95% sure). So I can only say S3 is at least about 85% accurate.
- For S2 (about 80%) the standard error with 20 questions is sqrt(0.8 × 0.2 / 20) = 0.09, so about ±9 percentage points, or ±2 questions. This fits what I saw (15 and 17).
- All 20 questions are the same kind (compare 2-3 districts with arithmetic), on one small made-up corpus, with one model and 2 runs. My conclusion is only for this kind of question. On other questions (no arithmetic, long texts) the ranking could be different (see C3).

**How many questions would I need?**
- To be sure that S3 is better than S2 (about 97% vs 80%) with the normal test (95% sure, 80% chance to see the difference), I would need about 70 questions per strategy.
- To measure the accuracy of S2 within ±5 percentage points I would need about 1.96² × 0.8 × 0.2 / 0.05² ≈ 250 questions.
- With 20 questions and 2 runs I trust the order S3 > S2 > S1 for this type of question, but I would not trust exact numbers like "S2 is 80% accurate".

### Final questions

1.
2.
3.
4.
5.
6.
7.
8.
