import google.generativeai as genai
import os
import sys

# Load API Key from secrets
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
    print("Could not find GOOGLE_API_KEY")
    exit(1)

genai.configure(api_key=key)


with open("available_models.txt", "w", encoding="utf-8") as f:
    f.write("Listing available models:\n")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                f.write(f"- {m.name}\n")
    except Exception as e:
        f.write(f"Error listing models: {e}\n")

print("Done writing to available_models.txt")
