"""
Fetch READMEs from GitHub for all ComfyUI custom nodes.

Usage:
    export GITHUB_TOKEN=your_github_token
    python fetch_readmes.py

This script:
1. Loads repos from nodes.json (created by fetch_data.py)
2. Fetches README content via GitHub GraphQL API (batched)
3. Strips markdown/HTML and cleans to plain text
4. Saves to readmes_cache.json
"""

import json
import os
import re
import urllib.request
import urllib.error
import time
import math

# Configuration
NODES_JSON = "nodes.json"
READMES_CACHE = "readmes_cache.json"
GRAPHQL_BATCH_SIZE = 50  # Repos per GraphQL query
MAX_README_CHARS = 2000

# API Keys
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')

if not GITHUB_TOKEN:
    print("ERROR: GITHUB_TOKEN environment variable is required.")
    exit(1)


def get_repo_path(url):
    """Extract owner/name from GitHub URL."""
    if not url:
        return None
    match = re.search(r'github\.com/([^/]+)/([^/]+)', url)
    if match:
        repo = match.group(2)
        if repo.endswith('.git'):
            repo = repo[:-4]
        return (match.group(1), repo)
    return None


def strip_markdown(text):
    """Remove markdown formatting, HTML tags, and common patterns."""
    if not text:
        return ''
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # Remove markdown images and links but keep link text
    text = re.sub(r'!\[[^\]]*\]\([^)]+\)', ' ', text)  # Images
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)  # Links -> keep text
    
    # Remove markdown badges (common in READMEs)
    text = re.sub(r'\[!\[.*?\]\(.*?\)\]\(.*?\)', ' ', text)
    
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', ' ', text)
    text = re.sub(r'`[^`]+`', ' ', text)
    
    # Remove headers markers
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    
    # Remove emphasis markers
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Bold
    text = re.sub(r'\*([^*]+)\*', r'\1', text)  # Italic
    text = re.sub(r'__([^_]+)__', r'\1', text)  # Bold
    text = re.sub(r'_([^_]+)_', r'\1', text)  # Italic
    
    # Remove blockquotes
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    
    # Remove horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    
    # Remove list markers
    text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)
    
    # Remove URLs
    text = re.sub(r'https?://[^\s]+', ' ', text)
    
    return text


def aggressive_clean(text):
    """Keep only essential characters: a-zA-Z0-9.-,"""
    if not text:
        return ''
    # Keep only allowed characters
    cleaned = re.sub(r'[^a-zA-Z0-9.\-,]', ' ', text)
    # Collapse multiple spaces
    cleaned = re.sub(r' +', ' ', cleaned)
    return cleaned.strip()


def process_readme(raw_text):
    """Full pipeline: strip markdown, aggressive clean, truncate."""
    if not raw_text:
        return ''
    
    # Step 1: Strip markdown/HTML
    text = strip_markdown(raw_text)
    
    # Step 2: Aggressive character filtering
    text = aggressive_clean(text)
    
    # Step 3: Truncate to max chars
    if len(text) > MAX_README_CHARS:
        text = text[:MAX_README_CHARS]
        # Try to break at a word boundary
        last_space = text.rfind(' ')
        if last_space > MAX_README_CHARS - 100:
            text = text[:last_space]
    
    return text


def fetch_readmes_graphql(repo_tuples):
    """Fetch README content for multiple repos in one GraphQL query."""
    url = 'https://api.github.com/graphql'
    headers = {
        'Authorization': f'bearer {GITHUB_TOKEN}',
        'Content-Type': 'application/json',
        'User-Agent': 'ComfyNodeBrowser/2.0'
    }
    
    query_parts = []
    for idx, owner, name in repo_tuples:
        # Try common README filenames
        query_parts.append(f"""
        r{idx}: repository(owner: "{owner}", name: "{name}") {{
            readme1: object(expression: "HEAD:README.md") {{
                ... on Blob {{ text }}
            }}
            readme2: object(expression: "HEAD:readme.md") {{
                ... on Blob {{ text }}
            }}
            readme3: object(expression: "HEAD:Readme.md") {{
                ... on Blob {{ text }}
            }}
        }}
        """)
    
    query = "query {\n" + "\n".join(query_parts) + "\n}"
    request_data = json.dumps({'query': query}).encode('utf-8')
    req = urllib.request.Request(url, data=request_data, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def load_readme_cache():
    """Load cached READMEs."""
    if os.path.exists(READMES_CACHE):
        with open(READMES_CACHE, 'r') as f:
            return json.load(f)
    return {}


def save_readme_cache(cache):
    """Save README cache."""
    with open(READMES_CACHE, 'w') as f:
        json.dump(cache, f)
    print(f"Saved {len(cache)} READMEs to cache")


def main():
    # Load nodes data
    if not os.path.exists(NODES_JSON):
        print(f"ERROR: {NODES_JSON} not found. Run fetch_data.py first.")
        exit(1)
    
    with open(NODES_JSON, 'r') as f:
        data = json.load(f)
    
    nodes = data.get('nodes', [])
    print(f"Loaded {len(nodes)} nodes from {NODES_JSON}")
    
    # Load README cache
    readme_cache = load_readme_cache()
    print(f"Loaded {len(readme_cache)} cached READMEs")
    
    # Build unique repo list
    all_repos = {}
    for node in nodes:
        ref = node.get('reference', '')
        parts = get_repo_path(ref)
        if parts:
            full_name = f"{parts[0]}/{parts[1]}"
            all_repos[full_name] = parts
    
    # Filter to repos needing fetch
    repos_needing_readme = {k: v for k, v in all_repos.items() if k not in readme_cache}
    
    print(f"Total unique repos: {len(all_repos)}")
    print(f"Repos needing README fetch: {len(repos_needing_readme)}")
    
    if not repos_needing_readme:
        print("All READMEs already cached!")
        return
    
    # Fetch READMEs
    print("\n=== Fetching READMEs ===")
    repos_list = list(repos_needing_readme.keys())
    
    for i in range(0, len(repos_list), GRAPHQL_BATCH_SIZE):
        batch = repos_list[i:i+GRAPHQL_BATCH_SIZE]
        batch_num = i // GRAPHQL_BATCH_SIZE + 1
        total_batches = math.ceil(len(repos_list) / GRAPHQL_BATCH_SIZE)
        print(f"Fetching batch {batch_num}/{total_batches}...")
        
        query_input = []
        batch_map = {}
        for b_idx, full_name in enumerate(batch):
            owner, name = repos_needing_readme[full_name]
            query_input.append((b_idx, owner, name))
            batch_map[b_idx] = full_name
        
        result = fetch_readmes_graphql(query_input)
        
        if result and 'data' in result:
            for b_idx, full_name in batch_map.items():
                alias = f"r{b_idx}"
                repo_data = result['data'].get(alias)
                if repo_data:
                    # Try each README variant
                    raw_text = None
                    for key in ['readme1', 'readme2', 'readme3']:
                        obj = repo_data.get(key)
                        if obj and obj.get('text'):
                            raw_text = obj['text']
                            break
                    
                    if raw_text:
                        cleaned = process_readme(raw_text)
                        if cleaned and len(cleaned) > 50:
                            readme_cache[full_name] = cleaned
                        else:
                            readme_cache[full_name] = None  # Mark as processed
                    else:
                        readme_cache[full_name] = None
                else:
                    readme_cache[full_name] = None
        
        # Save README cache every 10 batches
        if batch_num % 10 == 0:
            save_readme_cache(readme_cache)
        
        time.sleep(0.5)
    
    # Final save
    save_readme_cache(readme_cache)
    
    # Stats
    valid_readmes = sum(1 for v in readme_cache.values() if v is not None)
    print(f"\n=== Complete ===")
    print(f"Total cached: {len(readme_cache)}")
    print(f"Valid READMEs: {valid_readmes}")
    print(f"No README: {len(readme_cache) - valid_readmes}")


if __name__ == "__main__":
    main()
