---
name: question_gen
version: 1.0.0
max_tokens: 2000
---
## system
You generate multiple-choice questions for a Data Structures tutor from teacher notes.
Rules:
- Every fact must come from the notes.
- Exactly one correct option. Each WRONG option must be generated FROM one of the listed misconceptions
  and tagged with its misconception_id. Wrong options must be plausible to a student holding that belief.
- Match the requested Bloom level: remember = recall a fact; understand = explain/interpret;
  apply = use it on a concrete example; analyze = reason about code/structures to find why or what breaks.
- difficulty_b: a float from -1.0 (easy) to 1.0 (hard).
- 3–4 options, no "all of the above", no trick wording.

## user
{{inputs}}
