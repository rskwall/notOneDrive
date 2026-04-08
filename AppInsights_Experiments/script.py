import os
import json
import re
from pathlib import Path
from openai import OpenAI
from datetime import datetime, timezone

# ── Configuration ──────────────────────────────────────────────────────────────

BASE_DIR        = Path(__file__).parent
WORKFLOWS_DIR   = BASE_DIR / "Workflows"
PROMPTS_DIR     = BASE_DIR / "Prompt_Iterations"
OUTPUT_DIR      = BASE_DIR / "Prompt_2_Outputs"

# Change this to whichever prompt file you want to use
PROMPT_FILE     = PROMPTS_DIR / "prompt_2.json"

# Change this to the model you want to use (e.g. "gpt-4.1", "o3", etc.)
MODEL           = "gpt-5.4"

# Placeholder token inside the prompt's user message that gets replaced
# with the workflow text
WORKFLOW_PLACEHOLDER = "[INSERT WORKFLOW TEXT FILE HERE]"

# ── Helpers ────────────────────────────────────────────────────────────────────

def load_prompt_template(prompt_path: Path) -> dict:
    """Load and return the prompt JSON template."""
    with open(prompt_path, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_workflow_files(workflows_dir: Path) -> list[Path]:
    """Recursively collect all .txt files under the Workflows directory."""
    return sorted(workflows_dir.rglob("*.txt"))


def build_messages(template: dict, workflow_text: str) -> list[dict]:
    """
    Build the messages list for the Chat Completions API by injecting
    the workflow text into the user message placeholder.
    """
    user_content = template["user"].replace(WORKFLOW_PLACEHOLDER, workflow_text)
    messages = []

    if "system" in template:
        messages.append({"role": "system", "content": template["system"]})

    messages.append({"role": "user", "content": user_content})
    return messages


def sanitize_filename(name: str) -> str:
    """Remove characters that are invalid in Windows file names."""
    return re.sub(r'[<>:"/\\|?*]', "_", name)


def save_output(output_dir: Path, workflow_path: Path, response_text: str, metadata: dict) -> Path:
    """
    Save the model response as a JSON file inside OUTPUT_DIR,
    preserving the relative folder structure from WORKFLOWS_DIR.
    """
    try:
        relative = workflow_path.relative_to(WORKFLOWS_DIR)
    except ValueError:
        relative = Path(workflow_path.name)

    out_path = output_dir / relative.parent / (sanitize_filename(relative.stem) + "_output.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Try to parse the response as JSON first (model may return a JSON string).
    # If it is valid JSON, embed it as a structured object.
    # Otherwise split into lines so the file is human-readable.
    try:
        parsed_response = json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
        parsed_response = response_text.splitlines()

    output_data = {
        "workflow_file": str(workflow_path),
        "prompt_file":   str(PROMPT_FILE),
        "model":         MODEL,
        "timestamp":     datetime.now(timezone.utc).isoformat(),
        **metadata,
        "response":      parsed_response,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    return out_path


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    # Validate directories
    if not WORKFLOWS_DIR.exists():
        raise FileNotFoundError(f"Workflows directory not found: {WORKFLOWS_DIR}")
    if not PROMPT_FILE.exists():
        raise FileNotFoundError(f"Prompt file not found: {PROMPT_FILE}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load prompt template
    template = load_prompt_template(PROMPT_FILE)
    print(f"Loaded prompt template: {PROMPT_FILE.name}")

    # Collect workflow files
    workflow_files = collect_workflow_files(WORKFLOWS_DIR)
    if not workflow_files:
        print("No workflow .txt files found. Exiting.")
        return

    print(f"Found {len(workflow_files)} workflow file(s).\n")

    # Initialise OpenAI client (reads OPENAI_API_KEY from environment)
    client = OpenAI()

    results = []

    for i, wf_path in enumerate(workflow_files, start=1):
        print(f"[{i}/{len(workflow_files)}] Processing: {wf_path.relative_to(BASE_DIR)}")

        # Read workflow text
        try:
            workflow_text = wf_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  ERROR reading file: {e}\n")
            results.append({"file": str(wf_path), "status": "read_error", "error": str(e)})
            continue

        # Build messages and call the API
        messages = build_messages(template, workflow_text)

        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
            )
            response_text = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason
            usage = {
                "prompt_tokens":     response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens":      response.usage.total_tokens,
            }

        except Exception as e:
            print(f"  ERROR calling API: {e}\n")
            results.append({"file": str(wf_path), "status": "api_error", "error": str(e)})
            continue

        # Save output as JSON
        metadata = {"finish_reason": finish_reason, "usage": usage}
        out_path = save_output(OUTPUT_DIR, wf_path, response_text, metadata)
        print(f"  Saved → {out_path.relative_to(BASE_DIR)}  (finish_reason={finish_reason})\n")

        results.append({
            "file":          str(wf_path),
            "status":        "ok",
            "finish_reason": finish_reason,
            "usage":         usage,
            "output":        str(out_path),
        })

    # ── Summary ────────────────────────────────────────────────────────────────
    ok     = sum(1 for r in results if r["status"] == "ok")
    errors = len(results) - ok

    # Save run summary as JSON
    summary = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt_file":   str(PROMPT_FILE),
        "model":         MODEL,
        "total":         len(results),
        "succeeded":     ok,
        "failed":        errors,
        "results":       results,
    }
    summary_path = OUTPUT_DIR / "run_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("=" * 60)
    print(f"Done.  {ok} succeeded, {errors} failed.")
    print(f"Summary saved → {summary_path.relative_to(BASE_DIR)}")

    if errors:
        print("\nFailed files:")
        for r in results:
            if r["status"] != "ok":
                print(f"  {r['file']}  ({r['status']}: {r.get('error', '')})")


if __name__ == "__main__":
    main()