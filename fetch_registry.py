"""
Fetch data from Comfy Registry API and merge with existing nodes.

Usage:
    python fetch_registry.py

This script:
1. Loads existing nodes.json
2. Fetches all nodes from api.comfy.org/nodes
3. Matches by repository URL
4. Adds downloads and downloads/month (dpm) to existing nodes
5. Adds any missing nodes not in our data
6. Writes updated data back to nodes.js and nodes.json
"""

import json
import urllib.request
import urllib.error
import time
import re
from datetime import datetime

# Configuration
REGISTRY_API = "https://api.comfy.org/nodes"
NODES_JSON = "nodes.json"
OUTPUT_JS_FILE = "nodes.js"
OUTPUT_JSON_FILE = "nodes.json"
PAGE_SIZE = 100  # Max allowed by API


def normalize_repo_url(url):
    """Normalize GitHub URL to owner/repo format for matching."""
    if not url:
        return None
    # Handle various GitHub URL formats
    match = re.search(r'github\.com/([^/]+)/([^/\s\.]+)', url.lower())
    if match:
        owner = match.group(1)
        repo = match.group(2)
        if repo.endswith('.git'):
            repo = repo[:-4]
        return f"{owner}/{repo}"
    return None


def fetch_all_registry_nodes():
    """Fetch all nodes from Comfy Registry API with pagination."""
    all_nodes = []
    page = 1
    total_pages = None
    
    while True:
        url = f"{REGISTRY_API}?limit={PAGE_SIZE}&page={page}"
        print(f"Fetching page {page}" + (f"/{total_pages}" if total_pages else "") + "...")
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'ComfyNodeBrowser/2.0'})
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read())
                
                nodes = data.get('nodes', [])
                all_nodes.extend(nodes)
                
                total_pages = data.get('totalPages', 1)
                
                if page >= total_pages:
                    break
                    
                page += 1
                time.sleep(0.1)  # Be nice to the API
                
        except urllib.error.HTTPError as e:
            print(f"HTTP Error: {e.code}")
            break
        except Exception as e:
            print(f"Error: {e}")
            break
    
    print(f"Fetched {len(all_nodes)} nodes from Registry")
    return all_nodes


def calculate_dpm(downloads, created_at):
    """Calculate downloads per month."""
    if not downloads or not created_at:
        return 0
    
    try:
        # Parse ISO date
        created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        now = datetime.now(created.tzinfo)
        
        # Calculate months since creation
        diff_days = (now - created).days
        months = max(1, diff_days / 30.44)  # At least 1 month
        
        return downloads / months
    except Exception:
        return 0


def escape_html(text):
    """Escape HTML special characters."""
    if not text:
        return ''
    return (text
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&#039;'))


def format_date(ts):
    """Format timestamp for display."""
    if not ts or ts == 0:
        return '-'
    now = datetime.now()
    date = datetime.fromtimestamp(ts / 1000)
    diff_days = (now - date).days
    if diff_days <= 1:
        return 'Today'
    if diff_days <= 7:
        return f'{diff_days} days ago'
    if diff_days <= 30:
        weeks = diff_days // 7
        return f'{weeks} week{"s" if weeks != 1 else ""} ago'
    if diff_days <= 365:
        months = diff_days // 30
        return f'{months} month{"s" if months != 1 else ""} ago'
    return date.strftime('%b %d, %Y')


def generate_html_row(node):
    """Generate pre-rendered HTML row for a node."""
    stars_display = f'{node["stars"]:,}' if node["stars"] > 0 else '-'
    spm_display = str(round(node["spm"])) if node["spm"] > 0 else '-'
    dpm = node.get('dpm', 0)
    dpm_display = f'{int(dpm):,}' if dpm > 0 else '-'
    created_display = format_date(node["createdAtTs"])
    updated_display = format_date(node["lastUpdateTs"])
    
    title_escaped = escape_html(node['title'])
    author_escaped = escape_html(node['author'])
    desc_escaped = escape_html(node['description'])
    ref = node['reference']
    
    essential_tag = ' <b style="color:#38bdf8">★</b>' if node.get('id') == 'manager' else ''
    
    return f'''<tr><td><a href="{ref}" target="_blank"><b>{title_escaped}</b></a>{essential_tag} <small class="author-text">by {author_escaped}</small><br><small>{desc_escaped}</small></td><td class="stars">{stars_display}</td><td class="spm">{spm_display}</td><td class="dpm">{dpm_display}</td><td>{created_display}</td><td>{updated_display}</td></tr>'''


def main():
    # Load existing data
    print("Loading existing nodes.json...")
    try:
        with open(NODES_JSON, 'r') as f:
            existing_data = json.load(f)
    except FileNotFoundError:
        print("ERROR: nodes.json not found. Run fetch_data.py first.")
        return
    
    existing_nodes = existing_data.get('nodes', [])
    print(f"Loaded {len(existing_nodes)} existing nodes")
    
    # Build lookup by normalized repo URL
    repo_to_idx = {}
    for i, node in enumerate(existing_nodes):
        repo_key = normalize_repo_url(node.get('reference', ''))
        if repo_key:
            repo_to_idx[repo_key] = i
    
    # Fetch registry data
    registry_nodes = fetch_all_registry_nodes()
    
    # Build registry lookup by repo URL
    registry_by_repo = {}
    for rnode in registry_nodes:
        repo_key = normalize_repo_url(rnode.get('repository', ''))
        if repo_key:
            registry_by_repo[repo_key] = rnode
    
    # Merge data
    print("\nMerging data...")
    matched = 0
    new_nodes = []
    now = datetime.now()
    
    # Update existing nodes with registry data
    for i, node in enumerate(existing_nodes):
        repo_key = normalize_repo_url(node.get('reference', ''))
        if repo_key and repo_key in registry_by_repo:
            rnode = registry_by_repo[repo_key]
            downloads = rnode.get('downloads', 0) or 0
            created_at = rnode.get('created_at', '')
            
            dpm = calculate_dpm(downloads, created_at)
            
            existing_nodes[i]['downloads'] = downloads
            existing_nodes[i]['dpm'] = dpm
            # Cap monthsSinceUpdate at 18 for freshness filter
            if existing_nodes[i]['monthsSinceUpdate'] > 18:
                existing_nodes[i]['monthsSinceUpdate'] = 18
            existing_nodes[i]['html'] = generate_html_row(existing_nodes[i])
            matched += 1
        else:
            # No registry match
            existing_nodes[i]['downloads'] = 0
            existing_nodes[i]['dpm'] = 0
            # Cap monthsSinceUpdate at 18 for freshness filter
            if existing_nodes[i]['monthsSinceUpdate'] > 18:
                existing_nodes[i]['monthsSinceUpdate'] = 18
            existing_nodes[i]['html'] = generate_html_row(existing_nodes[i])
    
    print(f"Matched {matched} nodes with Registry data")
    
    # Find nodes in Registry but not in our data
    existing_repos = set(repo_to_idx.keys())
    registry_repos = set(registry_by_repo.keys())
    missing_repos = registry_repos - existing_repos
    
    print(f"Found {len(missing_repos)} nodes in Registry not in our data")
    
    # Add missing nodes
    for repo_key in missing_repos:
        rnode = registry_by_repo[repo_key]
        
        # Parse dates
        created_at = rnode.get('created_at', '')
        createdAtTs = 0
        lastUpdateTs = 0
        monthsSinceUpdate = 999
        spm = 0
        
        if created_at:
            try:
                dt_c = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                createdAtTs = int(dt_c.timestamp() * 1000)
                # NOTE: For Registry-only nodes, we don't have GitHub pushedAt data,
                # so we use created_at as lastUpdateTs. This is a known limitation.
                lastUpdateTs = createdAtTs
                
                diff = now.timestamp() - dt_c.timestamp()
                monthsSinceUpdate = min(18, int(diff / (60 * 60 * 24 * 30.44)))  # Cap at 18
                
                # Calculate stars per month
                stars = rnode.get('github_stars', 0) or 0
                months_age = max(1, diff / (60 * 60 * 24 * 30.44))
                spm = stars / months_age
            except Exception:
                pass
        
        downloads = rnode.get('downloads', 0) or 0
        dpm = calculate_dpm(downloads, created_at)
        
        new_node = {
            'author': rnode.get('publisher', {}).get('name', '') or rnode.get('author', 'Unknown'),
            'title': rnode.get('name', 'Unknown'),
            'reference': rnode.get('repository', ''),
            'description': rnode.get('description', ''),
            'id': rnode.get('id', ''),
            'stars': rnode.get('github_stars', 0) or 0,
            'spm': spm,
            'lastUpdateTs': lastUpdateTs,
            'createdAtTs': createdAtTs,
            'monthsSinceUpdate': monthsSinceUpdate,
            'downloads': downloads,
            'dpm': dpm,
            'searchStr': '',  # Will be set below
        }
        
        # Build search string
        new_node['searchStr'] = f"{new_node['title']} {new_node['author']} {new_node['description']}".lower()
        
        # Generate HTML
        new_node['html'] = generate_html_row(new_node)
        
        new_nodes.append(new_node)
    
    # Add new nodes to list
    existing_nodes.extend(new_nodes)
    print(f"Added {len(new_nodes)} new nodes from Registry")
    
    # Regenerate sorted indices
    print("Regenerating sorted indices...")
    indices = list(range(len(existing_nodes)))
    
    sorted_indices = {
        'stars_desc': sorted(indices, key=lambda i: existing_nodes[i]['stars'], reverse=True),
        'stars_asc': sorted(indices, key=lambda i: existing_nodes[i]['stars']),
        'spm_desc': sorted(indices, key=lambda i: existing_nodes[i]['spm'], reverse=True),
        'spm_asc': sorted(indices, key=lambda i: existing_nodes[i]['spm']),
        'updated_desc': sorted(indices, key=lambda i: existing_nodes[i]['lastUpdateTs'], reverse=True),
        'updated_asc': sorted(indices, key=lambda i: existing_nodes[i]['lastUpdateTs']),
        'created_desc': sorted(indices, key=lambda i: existing_nodes[i]['createdAtTs'], reverse=True),
        'created_asc': sorted(indices, key=lambda i: existing_nodes[i]['createdAtTs']),
        'name_asc': sorted(indices, key=lambda i: existing_nodes[i]['title'].lower()),
        'name_desc': sorted(indices, key=lambda i: existing_nodes[i]['title'].lower(), reverse=True),
        # New: downloads sorting
        'downloads_desc': sorted(indices, key=lambda i: existing_nodes[i]['downloads'], reverse=True),
        'downloads_asc': sorted(indices, key=lambda i: existing_nodes[i]['downloads']),
        'dpm_desc': sorted(indices, key=lambda i: existing_nodes[i]['dpm'], reverse=True),
        'dpm_asc': sorted(indices, key=lambda i: existing_nodes[i]['dpm']),
    }
    
    # Bundle output
    output_data = {
        'nodes': existing_nodes,
        'sortedIndices': sorted_indices,
        'generatedAt': now.strftime('%Y-%m-%d')
    }
    
    # Save
    print("Saving...")
    with open(OUTPUT_JSON_FILE, 'w') as f:
        json.dump(output_data, f)
        
    with open(OUTPUT_JS_FILE, 'w') as f:
        f.write(f'window.COMFY_DATA = {json.dumps(output_data)};')
    
    print(f"\n=== Complete ===")
    print(f"Total nodes: {len(existing_nodes)}")
    print(f"With Registry data: {matched}")
    print(f"New from Registry: {len(new_nodes)}")
    print(f"Saved to {OUTPUT_JS_FILE} and {OUTPUT_JSON_FILE}")


if __name__ == "__main__":
    main()
