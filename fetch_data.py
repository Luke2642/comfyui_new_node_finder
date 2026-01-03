import json
import os
import re
import urllib.request
import urllib.error
import time
import math
from datetime import datetime

# Configuration
NODES_URL = "https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-list.json"
DATA_FILE = "custom-node-list.json"
OUTPUT_JS_FILE = "nodes.js"
OUTPUT_JSON_FILE = "nodes.json"

# Token from environment variable (required for GraphQL API)
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
if not GITHUB_TOKEN:
    print("ERROR: GITHUB_TOKEN environment variable is required.")
    print("Set it with: export GITHUB_TOKEN=your_token_here")
    exit(1)

# GraphQL Query Template
# We will construct a query that fetches multiple repos at once using aliases
# query {
#   r0: repository(owner: "foo", name: "bar") { ... }
#   r1: repository(owner: "baz", name: "qux") { ... }
# }

def get_repo_path(url):
    if not url: return None
    match = re.search(r'github\.com/([^/]+)/([^/]+)', url)
    if match:
        repo = match.group(2)
        if repo.endswith('.git'):
            repo = repo[:-4]
        return (match.group(1), repo) # Return tuple (owner, name)
    return None

def fetch_details_graphql(repo_tuples, token):
    url = 'https://api.github.com/graphql'
    headers = {
        'Authorization': f'bearer {token}',
        'Content-Type': 'application/json',
        'User-Agent': 'ComfyNodeBrowser/2.0'
    }
    
    # helper to build query
    query_parts = []
    # repo_tuples is list of (index, owner, name) so we can map back
    for idx, owner, name in repo_tuples:
        # GraphQL aliases can't start with numbers or contain special chars, so we use r{idx}
        # We fetch stargazers count, pushed_at, created_at
        query_parts.append(f"""
        r{idx}: repository(owner: "{owner}", name: "{name}") {{
            stargazers {{
                totalCount
            }}
            pushedAt
            createdAt
        }}
        """)
        
    query = "query {\n" + "\n".join(query_parts) + "\n}"
    
    request_data = json.dumps({'query': query}).encode('utf-8')
    req = urllib.request.Request(url, data=request_data, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.read().decode()}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    print("Downloading node list...")
    try:
        req = urllib.request.Request(NODES_URL, headers={'User-Agent': 'ComfyNodeBrowser'})
        with urllib.request.urlopen(req) as response:
            raw_data = json.loads(response.read())
            # Save raw list as backup
            with open(DATA_FILE, 'w') as f:
                json.dump(raw_data, f, indent=2)
    except Exception as e:
        print(f"Failed to download node list: {e}")
        if os.path.exists(DATA_FILE):
            print("Using cached list.")
            with open(DATA_FILE, 'r') as f:
                raw_data = json.load(f)
        else:
            print("No data available.")
            return

    nodes = raw_data.get('custom_nodes', [])
    print(f"Processing {len(nodes)} nodes...")

    # Prepare batching
    # We need to map each node to its repo info
    # Some nodes share repos, but for simplicity we can just query for each node 
    # and cache by repo-string to avoid dupes in the query batch?
    # Better: Identify unique repos first.
    
    unique_repos = {} # "owner/name": { (owner, name) }
    repo_to_nodes = {} # "owner/name": [node_indices...]
    
    for i, node in enumerate(nodes):
        ref = node.get('reference', '')
        parts = get_repo_path(ref)
        if parts:
            owner, name = parts
            full_name = f"{owner}/{name}"
            unique_repos[full_name] = (owner, name)
            if full_name not in repo_to_nodes:
                repo_to_nodes[full_name] = []
            repo_to_nodes[full_name].append(i)
            
    sorted_repos = sorted(unique_repos.keys())
    total_repos = len(sorted_repos)
    print(f"Found {total_repos} unique GitHub repositories.")
    
    batch_size = 100    
    repo_data_map = {} # "owner/name" -> {stars, pushed_at, created_at}
    
    # Process batches
    for i in range(0, total_repos, batch_size):
        batch = sorted_repos[i:i+batch_size]
        print(f"Fetching batch {i//batch_size + 1}/{math.ceil(total_repos/batch_size)} ({len(batch)} repos)...")
        
        # Prepare list for query gen: [(idx, owner, name), ...]
        # We use simple index 0..N for the alias in this batch
        query_input = []
        batch_map = {} # alias_idx -> full_name
        
        for b_idx, full_name in enumerate(batch):
            owner, name = unique_repos[full_name]
            query_input.append((b_idx, owner, name))
            batch_map[b_idx] = full_name
            
        result = fetch_details_graphql(query_input, GITHUB_TOKEN)
        
        if result and 'data' in result:
            data = result['data']
            for b_idx, full_name in batch_map.items():
                alias = f"r{b_idx}"
                repo_info = data.get(alias)
                if repo_info:
                    repo_data_map[full_name] = {
                        'stars': repo_info['stargazers']['totalCount'],
                        'pushedAt': repo_info['pushedAt'],
                        'createdAt': repo_info['createdAt']
                    }
                else:
                    # Repo might be missing or private or renamed?
                    # GraphQL returns null for missing repos usually (or errors)
                    repo_data_map[full_name] = None
        else:
            print("Batch failed or returned no data.")
            if result and 'errors' in result:
                 print("Errors:", result['errors'][0]['message'])
            # Sleep a bit if error?
            time.sleep(1)


    # Consolidate Data
    print("Consolidating data...")
    final_nodes = []
    
    now = datetime.now()
    
    for i, node in enumerate(nodes):
        # Base fields we want to keep
        clean_node = {
            'author': node.get('author', 'Unknown'),
            'title': node.get('title', 'Unknown'),
            'reference': node.get('reference', ''),
            'description': node.get('description', ''),
            'id': node.get('id', '')
        }
        
        # Merge extra data
        ref = node.get('reference', '')
        parts = get_repo_path(ref)
        
        stars = 0
        spm = 0
        lastUpdateTs = 0
        createdAtTs = 0
        monthsSinceUpdate = 999
        
        if parts:
            full_name = f"{parts[0]}/{parts[1]}"
            r_data = repo_data_map.get(full_name)
            
            if r_data:
                stars = r_data['stars']
                
                # timestamps
                if r_data['pushedAt']:
                    dt_p = datetime.strptime(r_data['pushedAt'].replace('Z', '+0000'), "%Y-%m-%dT%H:%M:%S%z")
                    lastUpdateTs = int(dt_p.timestamp() * 1000)
                    
                    diff = now.timestamp() - dt_p.timestamp()
                    monthsSinceUpdate = int(diff / (60 * 60 * 24 * 30.44))
                    
                if r_data['createdAt']:
                    dt_c = datetime.strptime(r_data['createdAt'].replace('Z', '+0000'), "%Y-%m-%dT%H:%M:%S%z")
                    createdAtTs = int(dt_c.timestamp() * 1000)
                    
                    diff_stats = now.timestamp() - dt_c.timestamp()
                    months_age = max(1, diff_stats / (60 * 60 * 24 * 30.44))
                    spm = stars / months_age

        clean_node['stars'] = stars
        clean_node['spm'] = spm
        clean_node['lastUpdateTs'] = lastUpdateTs
        clean_node['createdAtTs'] = createdAtTs
        clean_node['monthsSinceUpdate'] = monthsSinceUpdate
        
        # Search string for UI - pre-calculate
        clean_node['searchStr'] = (f"{clean_node['title']} {clean_node['author']} {clean_node['description']}").lower()
        
        # Pre-render HTML row for instant DOM updates
        def escape_html(text):
            if not text:
                return ''
            return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#039;'))
        
        def format_date(ts):
            if not ts or ts == 0:
                return '-'
            from datetime import datetime
            date = datetime.fromtimestamp(ts / 1000)
            diff_days = (now - date).days
            if diff_days <= 1:
                return 'Today'
            if diff_days <= 7:
                return f'{diff_days} days ago'
            if diff_days <= 30:
                return f'{diff_days // 7} weeks ago'
            if diff_days <= 365:
                return f'{diff_days // 30} months ago'
            return date.strftime('%b %d, %Y')
        
        stars_display = f'{stars:,}' if stars > 0 else '-'
        spm_display = str(round(spm)) if spm > 0 else '-'
        created_display = format_date(createdAtTs)
        updated_display = format_date(lastUpdateTs)
        
        title_escaped = escape_html(clean_node['title'])
        author_escaped = escape_html(clean_node['author'])
        desc_escaped = escape_html(clean_node['description'])
        ref = clean_node['reference']
        
        essential_tag = ' <b style="color:#38bdf8">★</b>' if clean_node['id'] == 'manager' else ''
        
        # Minimal HTML - title, author, and description combined in one cell
        clean_node['html'] = f'''<tr><td><a href="{ref}" target="_blank"><b>{title_escaped}</b></a>{essential_tag} <small class="author-text">by {author_escaped}</small><br><small>{desc_escaped}</small></td><td class="stars">{stars_display}</td><td class="spm">{spm_display}</td><td>{created_display}</td><td>{updated_display}</td></tr>'''
        
        final_nodes.append(clean_node)

    # Pre-compute sorted indices for fast frontend rendering
    print("Pre-sorting indices...")
    
    # Create index arrays sorted by each field
    # Descending for stars/spm (higher is better), ascending for monthsSinceUpdate (fresher is better)
    indices = list(range(len(final_nodes)))
    
    sorted_indices = {
        # Stars: descending (most stars first)
        'stars_desc': sorted(indices, key=lambda i: final_nodes[i]['stars'], reverse=True),
        # Stars: ascending 
        'stars_asc': sorted(indices, key=lambda i: final_nodes[i]['stars']),
        # SPM: descending (highest growth rate first)
        'spm_desc': sorted(indices, key=lambda i: final_nodes[i]['spm'], reverse=True),
        # SPM: ascending
        'spm_asc': sorted(indices, key=lambda i: final_nodes[i]['spm']),
        # Months since update: ascending (most recently updated first = lower months)
        'updated_desc': sorted(indices, key=lambda i: final_nodes[i]['lastUpdateTs'], reverse=True),
        'updated_asc': sorted(indices, key=lambda i: final_nodes[i]['lastUpdateTs']),
        # Created: by timestamp
        'created_desc': sorted(indices, key=lambda i: final_nodes[i]['createdAtTs'], reverse=True),
        'created_asc': sorted(indices, key=lambda i: final_nodes[i]['createdAtTs']),
        # Name: alphabetical
        'name_asc': sorted(indices, key=lambda i: final_nodes[i]['title'].lower()),
        'name_desc': sorted(indices, key=lambda i: final_nodes[i]['title'].lower(), reverse=True),
    }
    
    # Bundle everything
    output_data = {
        'nodes': final_nodes,
        'sortedIndices': sorted_indices
    }
    
    # Saving
    with open(OUTPUT_JSON_FILE, 'w') as f:
        json.dump(output_data, f) # Minified by default (no indent)
        
    with open(OUTPUT_JS_FILE, 'w') as f:
        f.write(f'window.COMFY_DATA = {json.dumps(output_data)};')
        
    print(f"Saved {len(final_nodes)} nodes to {OUTPUT_JS_FILE} and {OUTPUT_JSON_FILE}")

if __name__ == "__main__":
    main()
