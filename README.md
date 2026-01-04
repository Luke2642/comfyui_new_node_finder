# ComfyUI New Node Finder

A modern, responsive web application for browsing and discovering [ComfyUI](https://github.com/comfyanonymous/ComfyUI) custom nodes. Filter, search, and sort through the entire ecosystem to find the perfect nodes for your workflow.

![License](https://img.shields.io/badge/license-MIT-blue.svg)

---

## ✅ Working Features

### 🌐 Web Interface (`index.html`)
- **📊 Real-time Filtering** - Filter nodes by stars, star velocity, download velocity, and freshness (months since update)
- **🔍 Instant Search** - Search across node names, authors, and descriptions
- **📈 Smart Metrics** - View GitHub stars, star velocity (stars/month), and download velocity (downloads/month)
- **🔄 Multi-column Sorting** - Click column headers to sort by any metric (ascending/descending)
- **⚡ Fast Performance** - Pre-rendered HTML rows and 14 pre-sorted indices for instant UI updates
- **🎨 Modern UI** - Glassmorphism design with smooth animations and dark mode
- **📱 Responsive Mobile View** - Card-based layout on mobile with clear stat labels

### 📦 Data Pipeline

| Script | Status | Description |
|--------|--------|-------------|
| `fetch_registry.py` | ✅ Working | Fetches download stats from Comfy Registry API, calculates downloads/month, merges with existing data |
| `fetch_data.py` | ✅ Working | Fetches node metadata from ComfyUI-Manager + GitHub stats (stars, dates) via GraphQL API. Merges with existing nodes.json to preserve Registry data |
| `fetch_readmes.py` | ✅ Working | Batch-fetches README content for all repos via GitHub GraphQL, strips markdown, and caches cleaned text |
| `generate_summaries.py` | 🔄 In Progress | Uses LLM (GPT-4o-mini via GitHub Models API) to generate categorized summaries from READMEs |

### 📊 Current Data Stats
- **4,579 total nodes** indexed
- **3,758 nodes** with GitHub stars data
- **2,226 nodes** with Registry download data
- **3,877 README files** cached and processed
- **25 categories** defined for classification
- **14 sort indices** pre-computed for fast sorting

---

## 🚧 Work in Progress

### LLM-Based Categorization & Summaries
The `generate_summaries.py` script is designed to:
- Classify each node into 1-5 categories from a predefined list (`categories.txt`)
- Generate concise 30-word summaries of what each node does
- Cache results in `summaries_cache.json`

**Current status**: ~153 repos have old-format summaries (plain text). The new format with categories is implemented but requires re-processing.

---

## 🖥️ Live Demo

Simply open `index.html` in your browser to explore the node ecosystem.

## 🚀 Getting Started

### Viewing the Explorer

1. Clone the repository:
   ```bash
   git clone https://github.com/Luke2642/comfyui_node_browser.git
   cd comfyui_node_browser
   ```

2. Open `index.html` in your browser - that's it!

### Updating the Data

The node data is aggregated from [ComfyUI-Manager](https://github.com/ltdrdata/ComfyUI-Manager), [Comfy Registry](https://api.comfy.org/nodes), and GitHub.

**Recommended order** (to get both download stats and GitHub data for all nodes):

#### 1. Fetch Registry Data (Downloads)
```bash
python fetch_registry.py
```
Fetches download counts from Comfy Registry API and calculates downloads/month velocity.

#### 2. Fetch GitHub Data (Stars, Dates)
```bash
export GITHUB_TOKEN=your_github_token_here
python fetch_data.py
```
Downloads the latest node list from ComfyUI-Manager, merges with existing nodes.json, and fetches GitHub statistics for ALL nodes.

#### 3. Fetch README Content (Optional)
```bash
export GITHUB_TOKEN=your_github_token_here
python fetch_readmes.py
```
Batch-fetches and caches README content for all repositories.

#### 4. Generate Summaries (Optional)
```bash
export GITHUB_MODELS_TOKEN=your_github_models_token
python generate_summaries.py
```
Uses LLM to generate categorized summaries (rate-limited, runs incrementally).

## 📁 Project Structure

```
comfy_node_browser/
├── index.html              # Main web application
├── fetch_registry.py       # Fetch download stats from Comfy Registry
├── fetch_data.py           # Fetch node metadata + GitHub stats (merges with existing data)
├── fetch_readmes.py        # Fetch and cache README content
├── generate_summaries.py   # LLM-based categorization & summaries
├── categories.txt          # 25 category definitions for classification
├── nodes.js                # Generated: Node data for browser
├── nodes.json              # Generated: Node data as JSON
├── custom-node-list.json   # Cached: Raw node list from ComfyUI-Manager
├── readmes_cache.json      # Cached: Processed README content
└── summaries_cache.json    # Cached: LLM-generated summaries (in progress)
```

## 🔧 How It Works

### Data Pipeline

1. **Registry Fetch** - Fetches download stats from Comfy Registry API, calculates downloads/month
2. **Manager Fetch** - Downloads node list from ComfyUI-Manager, merges with existing data
3. **GitHub Enrich** - Uses GitHub's GraphQL API to batch-fetch stars, pushedAt, createdAt for all repos
4. **Metrics** - Calculates star velocity (stars/month), download velocity (downloads/month), freshness
5. **Pre-render** - Generates HTML rows and 14 sorted index arrays
6. **READMEs** - Fetches, cleans (strips markdown), and truncates README content
7. **Summarize** - (WIP) Uses LLM to categorize and describe each node

### Frontend Optimizations

- **Pre-rendered HTML**: Each node's table row is pre-generated server-side for instant DOM updates
- **Pre-sorted indices**: 14 sort orders pre-computed (stars, spm, dpm, downloads, created, updated, name - both asc/desc)
- **Debounced rendering**: 300ms debounce on sliders to prevent UI stuttering
- **Minimal DOM manipulation**: Uses `innerHTML` with prepared strings instead of individual element creation

## 📊 Metrics Explained

| Metric | Description |
|--------|-------------|
| **Stars** | Total GitHub stars for the repository |
| **Star Velocity** | Stars gained per month since creation - find trending nodes |
| **Download Velocity** | Downloads per month from Comfy Registry - measures actual usage |
| **Created** | When the repository was first created |
| **Last Update** | When the repository was last pushed to |

## 🎨 UI Controls

| Filter | Range | Description |
|--------|-------|-------------|
| **Search** | - | Filter by name, author, or description |
| **Stars** | 0-3,000 | Minimum GitHub stars |
| **Star Velocity** | 0-300 | Minimum stars/month growth rate |
| **Download Velocity** | 0-10,000 | Minimum downloads/month |
| **Freshness** | 0-18 mo | Maximum months since last update |

Click any **column header** to sort (toggles ascending/descending).

## 📝 License

MIT License - feel free to use, modify, and distribute.

## 🙏 Acknowledgments

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - The amazing node-based Stable Diffusion UI
- [ComfyUI-Manager](https://github.com/ltdrdata/ComfyUI-Manager) - For maintaining the comprehensive custom node registry
- [Comfy Registry](https://api.comfy.org) - For download statistics and additional node metadata
