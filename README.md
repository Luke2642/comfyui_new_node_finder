# ComfyUI Custom Node Explorer

A modern, responsive web application for browsing and discovering [ComfyUI](https://github.com/comfyanonymous/ComfyUI) custom nodes. Filter, search, and sort through the entire ecosystem to find the perfect nodes for your workflow.

![License](https://img.shields.io/badge/license-MIT-blue.svg)

## ✨ Features

- **📊 Real-time Filtering** - Filter nodes by minimum stars, stars per month (growth rate), and recency of updates
- **🔍 Instant Search** - Search across node names, authors, and descriptions
- **📈 Smart Metrics** - View GitHub stars and "Stars per Month" to discover trending or established nodes
- **⚡ Fast Performance** - Pre-rendered HTML and pre-sorted indices for instant UI updates
- **🎨 Modern UI** - Glassmorphism design with smooth animations and dark mode
- **📱 Responsive** - Works seamlessly on desktop and mobile devices

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

The node data is fetched from [ComfyUI-Manager](https://github.com/ltdrdata/ComfyUI-Manager) and enriched with GitHub statistics. To refresh the data:

1. Set your GitHub token (required for API access):
   ```bash
   export GITHUB_TOKEN=your_github_token_here
   ```

2. Run the fetch script:
   ```bash
   python fetch_data.py
   ```

This will:
- Download the latest `custom-node-list.json` from ComfyUI-Manager
- Fetch GitHub statistics (stars, last push date, creation date) via GraphQL API
- Generate `nodes.js` and `nodes.json` with enriched, pre-processed data

## 📁 Project Structure

```
comfy_node_browser/
├── index.html           # Main web application
├── fetch_data.py        # Python script to fetch and process node data
├── nodes.js             # Generated: Node data as JS for browser consumption
├── nodes.json           # Generated: Node data as JSON
└── custom-node-list.json # Cached: Raw node list from ComfyUI-Manager
```

## 🔧 How It Works

### Data Pipeline

1. **Fetch** - Downloads the official node list from ComfyUI-Manager's GitHub repository
2. **Enrich** - Uses GitHub's GraphQL API to batch-fetch repository metadata (stars, dates)
3. **Process** - Calculates derived metrics like "stars per month" and pre-renders HTML rows
4. **Pre-sort** - Creates sorted index arrays for each sortable column (both ascending and descending)

### Frontend Optimizations

- **Pre-rendered HTML**: Each node's table row is pre-generated server-side for instant DOM updates
- **Pre-sorted indices**: Sorting uses pre-computed index arrays instead of runtime sorting
- **Debounced rendering**: Slider changes batch updates to prevent UI stuttering
- **Minimal DOM manipulation**: Uses `innerHTML` with prepared strings instead of individual element creation

## 📊 Metrics Explained

| Metric | Description |
|--------|-------------|
| **Stars** | Total GitHub stars for the repository |
| **Stars/Month** | Average stars gained per month since repository creation - useful for finding trending nodes |
| **Created** | When the repository was first created |
| **Last Update** | When the repository was last pushed to |

## 🎨 UI Controls

- **Search**: Filter by name, author, or description
- **Min Stars**: Only show nodes with at least this many stars
- **Min Stars/Month**: Only show nodes with at least this growth rate (good for finding trending nodes)
- **Max Months Since Update**: Filter out stale/unmaintained nodes

## 📝 License

MIT License - feel free to use, modify, and distribute.

## 🙏 Acknowledgments

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - The amazing node-based Stable Diffusion UI
- [ComfyUI-Manager](https://github.com/ltdrdata/ComfyUI-Manager) - For maintaining the comprehensive custom node registry
