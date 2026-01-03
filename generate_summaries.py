"""
Categorize and summarize ComfyUI custom nodes using GitHub Models API.

Usage:
    export GITHUB_MODELS_TOKEN=your_github_token
    python generate_summaries.py

Output format per repo:
{
    "categories": ["category1", "category2"],
    "summary": "What it does without filler words"
}
"""

import json
import os
import time
import urllib.request
import urllib.error

# Configuration
READMES_CACHE = "readmes_cache.json"
SUMMARIES_CACHE = "summaries_cache.json"
CATEGORIES_FILE = "categories.txt"

# GitHub Models config
MODEL = "gpt-4o-mini"
GITHUB_MODELS_ENDPOINT = "https://models.inference.ai.azure.com/chat/completions"
RPM_LIMIT = 10

# API Key
GITHUB_MODELS_TOKEN = os.environ.get('GITHUB_MODELS_TOKEN')

if not GITHUB_MODELS_TOKEN:
    print("ERROR: GITHUB_MODELS_TOKEN environment variable is required.")
    exit(1)


def load_categories():
    """Load category definitions from file."""
    categories = {}
    with open(CATEGORIES_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if line and line.startswith('['):
                # Parse [category_name]description
                bracket_end = line.find(']')
                if bracket_end > 0:
                    cat_name = line[1:bracket_end]
                    cat_desc = line[bracket_end+1:]
                    categories[cat_name] = cat_desc
    return categories


def build_system_prompt(categories):
    """Build system prompt with category list."""
    cat_list = "\n".join([f"- {name}: {desc}" for name, desc in categories.items()])
    
    return f"""You are a technical classifier for software projects. Your task is to:
1. Assign 1-5 categories from the list below
2. Write a concise summary (max 30 words) of what the software does

RULES:
- Never use the words "node", "nodes", "ComfyUI", or "comfy"
- No filler phrases like "This project...", "A collection of...", "Tools for..."
- Start directly with a verb or noun describing functionality
- Be specific and technical

CATEGORIES:
{cat_list}

RESPOND IN EXACTLY THIS JSON FORMAT:
{{"categories": ["cat1", "cat2"], "summary": "Direct description of functionality"}}"""


def call_github_models(system_prompt, text):
    """Call GitHub Models API."""
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {GITHUB_MODELS_TOKEN}'
    }
    
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        "max_tokens": 200,
        "temperature": 0.2
    }
    
    request_data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(GITHUB_MODELS_ENDPOINT, data=request_data, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read())
            choices = result.get('choices', [])
            if choices:
                message = choices[0].get('message', {})
                content = message.get('content', '').strip()
                # Parse JSON response
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    # Try to extract JSON from response
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    if start >= 0 and end > start:
                        return json.loads(content[start:end])
                    return None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        if e.code == 429:
            print(f"RATE LIMITED - waiting 60s...")
            time.sleep(60)
            return "RATE_LIMITED"
        elif e.code == 401:
            print(f"AUTH ERROR")
            return "AUTH_ERROR"
        print(f"Error: {e.code} - {error_body[:200]}")
    except Exception as e:
        print(f"Error: {e}")
    
    return None


def load_summaries_cache():
    """Load existing summaries."""
    if os.path.exists(SUMMARIES_CACHE):
        with open(SUMMARIES_CACHE, 'r') as f:
            return json.load(f)
    return {}


def save_summaries_cache(cache):
    """Save summaries cache."""
    with open(SUMMARIES_CACHE, 'w') as f:
        json.dump(cache, f, indent=2)


def load_readme_cache():
    """Load cached READMEs."""
    if os.path.exists(READMES_CACHE):
        with open(READMES_CACHE, 'r') as f:
            return json.load(f)
    return {}


def main():
    print(f"Using model: {MODEL}")
    
    # Load categories
    categories = load_categories()
    print(f"Loaded {len(categories)} categories")
    system_prompt = build_system_prompt(categories)
    
    # Load README cache
    readme_cache = load_readme_cache()
    if not readme_cache:
        print(f"ERROR: {READMES_CACHE} not found. Run fetch_readmes.py first.")
        exit(1)
    
    valid_readmes = {k: v for k, v in readme_cache.items() if v is not None}
    print(f"Loaded {len(valid_readmes)} valid READMEs")
    
    # Load existing summaries
    summaries_cache = load_summaries_cache()
    
    # Filter to only repos that need NEW format (have categories)
    # Re-process old string summaries
    repos_to_process = []
    for name, text in valid_readmes.items():
        if name not in summaries_cache:
            repos_to_process.append((name, text))
        elif isinstance(summaries_cache[name], str):
            # Old format - needs reprocessing
            repos_to_process.append((name, text))
    
    print(f"Existing summaries: {len(summaries_cache)}")
    print(f"Repos needing (re)processing: {len(repos_to_process)}")
    
    if not repos_to_process:
        print("All repos already processed!")
        return
    
    processed = 0
    successful = 0
    errors = 0
    
    for full_name, cleaned_text in repos_to_process:
        processed += 1
        print(f"[{processed}/{len(repos_to_process)}] {full_name[:50]}...", end=" ")
        
        result = call_github_models(system_prompt, cleaned_text)
        
        if result == "RATE_LIMITED":
            result = call_github_models(system_prompt, cleaned_text)
        
        if result == "AUTH_ERROR":
            print("\nStopping due to auth error.")
            break
        elif result and isinstance(result, dict):
            summaries_cache[full_name] = result
            successful += 1
            cats = result.get('categories', [])
            summary = result.get('summary', '')[:50]
            print(f"OK [{', '.join(cats[:3])}] {summary}...")
            save_summaries_cache(summaries_cache)
        else:
            errors += 1
            print("ERROR")
        
        time.sleep(60 / RPM_LIMIT)
    
    print(f"\n=== Session Complete ===")
    print(f"Processed: {processed}")
    print(f"Successful: {successful}")
    print(f"Errors: {errors}")
    
    # Count properly formatted entries
    proper = sum(1 for v in summaries_cache.values() if isinstance(v, dict))
    print(f"\nProperly formatted: {proper}")
    print(f"Remaining: {len(valid_readmes) - proper}")


if __name__ == "__main__":
    main()
