import json
from pathlib import Path

TAB_CONFIG_PATH = Path(__file__).parent / "tab_config.json"
DELEGATE_CONFIG_PATH = Path(__file__).parent / "delegate_config.json"

with open(TAB_CONFIG_PATH, "r", encoding="utf-8") as f:
    tab_config = json.load(f)

with open(DELEGATE_CONFIG_PATH, "r", encoding="utf-8") as f:
    delegate_config = json.load(f)