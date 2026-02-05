# app/agent/util.py
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def get_prompt(filename: str) -> str:
    prompt_path = BASE_DIR / "prompts" / filename

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")

    return prompt_path.read_text(encoding="utf-8")
