# Copilot Instructions

## Project Purpose

This is an AI experimentation project that feeds recorded **IBM i (5250) and mainframe (3270)** terminal session files through LLM APIs to generate reusable, generic, step-by-step keyboard navigation instructions. The goal is to evaluate how well different models and prompt variants extract workflow patterns from raw terminal traces.

## Running the Scripts

### `copilot_run.py` — uses GitHub Copilot credentials (recommended)

```bash
# Authenticate once with gh CLI (only needed the first time)
gh auth login

# Interactive prompt selection
python copilot_run.py

# Or pass flags directly
python copilot_run.py --prompt prompt_2.json --model gpt-4.1
```

Uses the same GitHub token that powers Copilot (`gh auth token`). Outputs go to `Copilot_Outputs/<model-name>/`, mirroring the `Workflows/` directory structure.

Available `--model` values (GitHub Models): `gpt-4.1`, `o3`, `claude-3-5-sonnet`, `meta-llama-3.1-70b-instruct`

### `script.py` — uses OpenAI API key directly

```bash
# Requires OPENAI_API_KEY in the environment
python script.py
```

Configured via constants at the top of the file (`MODEL`, `PROMPT_FILE`, `OUTPUT_DIR`). Outputs go to `Prompt_2_Outputs/`.

**Dependency for both scripts:** `pip install openai`

## Architecture

```
Workflows/          # Input: raw terminal recordings (.txt), organized by system
  LEGADEMO/         #   IBM i 5250 terminal sessions (LegaSuite demo app)
  Db2 Admin/        #   Mainframe Db2 Admin 3270 terminal sessions
  (Z_OS/Workflows/) #   z/OS ISPF-style sessions (separate subfolder)

Prompt_Iterations/  # Prompt templates (JSON with "system" and "user" keys)
  prompt_1.txt      #   Legacy plain-text prompt (not used by script.py)
  prompt_2.json     #   Current prompt for LEGADEMO — outputs structured JSON steps
  prompt_2_db2.json #   Variant for Db2 Admin — outputs plain numbered list

Prompt_2_Outputs/   # script.py output: mirrors Workflows/ structure
  LEGADEMO/         #   One *_output.json per workflow file
  Db2 Admin/        #   Plus a run_summary.json at root

# Model-comparison output folders (manual / curated)
Claude4.6/          # Claude 4.6 Opus and Sonnet responses (plain text)
Default_Copilot/    # GitHub Copilot responses (plain text)
GPT-4.1/            # GPT-4.1 responses (plain text)
GPT-5.4/            # GPT-5.4 responses (plain text)
Prompt_1_Outputs/   # Older prompt_1 outputs

XML_Screens/        # 5250 screen XML definitions (field layout reference)
```

## Key Conventions

### Prompt template format

Prompt files are JSON with `"system"` and `"user"` keys. The user message contains a placeholder that `script.py` replaces at runtime with the workflow file contents:

- `prompt_2.json` uses: `[INSERT WORKFLOW TEXT FILE HERE]`
- `prompt_2_db2.json` uses: `{{INSERT WORKFLOW FILE HERE}}` ← different syntax, not handled by the current script

### Output JSON schema (`Prompt_2_Outputs/`)

Each output file contains:
```json
{
  "workflow_file": "...",
  "prompt_file": "...",
  "model": "...",
  "timestamp": "ISO-8601 UTC",
  "finish_reason": "stop",
  "usage": { "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0 },
  "response": { }   // parsed JSON object if model returned valid JSON, else array of lines
}
```

### Structured step schema (prompt_2.json target output)

`prompt_2.json` instructs the model to return a JSON object:
```json
{
  "workflow_name": "...",
  "steps": [
    { "step": 1, "type": "key",           "description": "...", "key": "Enter" },
    { "step": 2, "type": "type",          "description": "...", "text": "legademo", "row": 19, "col": 7 },
    { "step": 3, "type": "type_variable", "description": "...", "placeholder": "[Customer Number]", "row": 3, "col": 31 }
  ]
}
```
- `key` — press a function/control key, no text entry
- `type` — enter a constant literal value at a specific screen position (0-based row/col)
- `type_variable` — placeholder for a user-supplied value at a screen position

### Workflow file format

Terminal recordings are 80×24 screen dumps with `CCSID 37`. Each state block shows the screen render with 0-based row numbers on the left. The files include internal metadata (host states, call stacks, open files) that prompts explicitly instruct the model to ignore.

### Two workflow systems

- **LEGADEMO**: IBM i 5250, always starts from the LEGADEMO main menu, uses `prompt_2.json`
- **Db2 Admin**: Mainframe 3270/5250 hybrid, starts from the Db2 Admin main menu, uses `prompt_2_db2.json`
