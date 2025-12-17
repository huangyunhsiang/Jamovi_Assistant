import google.generativeai as genai
import os
import sys

# Redirect stdout/stderr to a file
log_file = open("gemini_log_v2.txt", "w", encoding="utf-8")
sys.stdout = log_file
sys.stderr = log_file

key = None
try:
    with open(".streamlit/secrets.toml", "r", encoding="utf-8") as f:
        for line in f:
            if "GOOGLE_API_KEY" in line:
                key = line.split("=")[1].strip().strip('"').strip("'")
                break
except Exception as e:
    print(f"Error loading secrets: {e}")
    exit(1)

if not key:
    print("Could not find GOOGLE_API_KEY in .streamlit/secrets.toml")
    exit(1)

print(f"Loaded key: {key[:5]}...{key[-5:]}")
genai.configure(api_key=key)

print("\nTesting generation with 'gemini-2.5-flash'...")
try:
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content("Hello, do you work?", request_options={'timeout': 10})
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error with gemini-2.5-flash: {e}")

log_file.close()
