# Quiz Authoring Cheat Sheet

Write quizzes as Markdown files in `experiments/<experiment>/ui/quiz/` (one quiz per file).
The quiz page auto‑detects files and lets you choose which one to run.

## File Placement

- Put files under `experiments/<experiment>/ui/quiz/`: e.g., `experiments/<experiment>/ui/quiz/questions.md`, `experiments/<experiment>/ui/quiz/derivatives.md`.
- The quiz name is the file name (without `.md`) (used in logs and stats).

## Question Structure

- Header: `## Question <number>: <id>`
  - Example: `## Question 1: q1`
- Prompt: first bold line under the header is taken as the question text.
  - Example: `**What is d/dx (x^2)?**`

## Choices and Type

- Single‑choice (radio): start lines with `A)`, `B)`, `C)`, ...
- Multi‑choice (checkbox): start lines with `A]`, `B]`, `C]`, ...
- Mark correct choices with a trailing `✓` (outside code).
- Type is determined only by the marker: `)` = radio, `]` = checkbox — number of ✓ does not affect type.

Examples:

Single (radio)

```
## Question 1: q1
**Derivative of x^2**
A) x
B) 2x ✓
C) x^3
D) constant
```

Multi (checkbox)

```
## Question 2: q2
**Pick primes**
A] 2 ✓
B] 3 ✓
C] 4
D] 9
```

## Markdown, Code, and Math

- Inline code: `` `like this` ``
- Fenced code blocks:
  ```
  ```python
  def f(x):
      return x*x
  ```
  ```
- LaTeX math: `$...$` (inline), `$$...$$` (display)
- Raw HTML is ignored/stripped for safety.
- Choice markers and ✓ inside fenced code blocks are ignored by the parser.

## Logging and Stats

- Every submission is logged via `/call` with `func_name='echo'`.
- Payload includes: `quizname`, `qid`, `question`, and either:
  - Single: `type:'single', choice_index, choice_text`
  - Multi: `type:'multi', choice_indices:[...], choice_texts:[...]`
- View charts at `/exp/<experiment>/ui/quiz-stats.html?quiz=<quizname>[&trial=<label>]`.
  - Dedupe by latest per student; CSV export available.
  - When exactly 10,000 logs are returned, a truncation banner is shown.

## Tips

- Keep prompts succinct; long code/math still works but titles are truncated in places.
- Use a Trial label on the quiz page to separate runs (helps stats).
- Registration pill checks `GET /is-registered?student_id=...` for the active experiment.
- If the quiz dropdown looks empty, ensure the server’s `/exp/<experiment>/files?ext=md&dir=quiz` is reachable; the UI falls back to probing `quiz/questions.md`, `quiz/derivatives.md`.

That’s it — save the `.md` file and refresh the quiz page.
