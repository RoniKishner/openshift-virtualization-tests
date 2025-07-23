import os
import subprocess
import requests
import json

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

base = os.environ.get("GITHUB_BASE_REF")
head = os.environ.get("GITHUB_HEAD_REF")

print(f"Comparing changes: {base}...{head}")

# Get changed files
result = subprocess.run(
    ["git", "diff", "--name-only", f"{base}...{head}"],
    capture_output=True,
    text=True
)

print("Changed files raw output:\n", result.stdout)

changed_files = [f for f in result.stdout.splitlines() if f.endswith(".py")]

if not changed_files:
    print("No Python files changed. Nothing to review.")
    exit(0)
else:
    print("Python files to review:", changed_files)

# Gemini endpoint
url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-pro:generateContent?key={GEMINI_API_KEY}"
headers = { "Content-Type": "application/json" }

for filename in changed_files:
    try:
        with open(filename, "r") as f:
            content = f.read()
    except Exception as e:
        print(f"Failed to read {filename}: {e}")
        continue

    prompt = f"""
        provide a summary and analysis of this file:
        
        Filename: {filename}
        
        Code:
        {content}
    """

    data = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ]
    }

    print(f"\n📝 Review for `{filename}`:")

    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        print(f"❌ API error: {response.status_code} - {response.text}")
        continue

    try:
        output = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        print(output.strip())
    except (KeyError, IndexError) as e:
        print("❌ Failed to parse Gemini response:", response.json())
