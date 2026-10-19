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

- Round limit, and why:
- Where the logs are:
- Real Q-09 conversation compared with my A3 version, what is different:

### B4 — Three strategies

**What I kept the same:**

<!-- model, temperature, k, prompts, answer format, anything else -->

**My rule for a correct answer** (written before the first full run):

| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 direct | | | | | | | |
| 1 | S2 think and vote (k = ) | | | | | | | |
| 1 | S3 tools | | | | | | | |
| 2 | S1 direct | | | | | | | |
| 2 | S2 think and vote (k = ) | | | | | | | |
| 2 | S3 tools | | | | | | | |

**Per question (run 1):**

| Question | S1 | S2 | S3 |
|---|:---:|:---:|:---:|
| Q-01 | | | |
| Q-02 | | | |
| Q-03 | | | |
| Q-04 | | | |
| Q-05 | | | |
| Q-06 | | | |
| Q-07 | | | |
| Q-08 | | | |
| Q-09 | | | |
| Q-10 | | | |
| Q-11 | | | |
| Q-12 | | | |
| Q-13 | | | |
| Q-14 | | | |
| Q-15 | | | |
| Q-16 | | | |
| Q-17 | | | |
| Q-18 | | | |
| Q-19 | | | |
| Q-20 | | | |

---

## Part C — Explain and choose (Hard)

### C1 — Does the tool description matter?

| Question | Calls (your description) | Calls (vague) | Answer (yours) | Answer (vague) |
|---|---:|---:|---|---|
| | | | | |

### C2 — Three mistakes explained

### C3 — Which strategy I would use, and what would change it

### C4 — How sure I can be

### Final questions

1.
2.
3.
4.
5.
6.
7.
8.
