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

#### `lookup`

```json
```

| Case | What the tool returns |
|---|---|
| success | |
| | |

**Worst thing it could do with strange or dangerous input:**

#### `calculate`

```json
```

| Case | What the tool returns |
|---|---|
| success | |
| | |

**Worst thing it could do with strange or dangerous input:**

### A3 — Q-09 by hand

```json
```

**My arithmetic:**

### A4 — Why I split it this way

<!-- one other way to split the task, and why you did not choose it -->

---

## Part B — Build it and run it (Medium)

### What I changed from Part A while coding

<!-- what changed in your plan, and why. "None" is an answer too. -->

### B2 — Tests

```text
<!-- pytest output -->
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
