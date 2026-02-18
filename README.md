# LuxWeb: Industrial Silicon Photonics Agent 🚀

LuxWeb is the intelligent interface for the **Lux-KB** (Knowledge Base). It uses a local RAG (Retrieval-Augmented Generation) pipeline to provide "Fab-Aware" insights and technical summaries from internal Silicon Photonics research papers.

## 🛠️ Tech Stack
- **Engine:** [Ollama](https://ollama.com/) (Local LLM Runtime)
- **Model:** **Gemma 3** — Optimized for technical reasoning and local efficiency.
- **Framework:** LangChain (LCEL)
- **Vector Store:** ChromaDB (Linked from `lux-kb`)

---

## 🚀 Quick Start

### 0. Set up the Environment
We use `uv` for ultra-fast, isolated virtual environments.
```bash
# Create the environment
uv venv --python 3.12
```
# (Optional) Activate it
```bash
source .venv/bin/activate
```
# Install requirements
```bash
uv pip install -r requirements.txt
```

### 1. Prerequisites
Ensure you have **Ollama** installed and running on your host machine or WSL2.
```bash
# Verify installation
ollama --version
```
### 2. Download the Model 
The agent requires the Gemma 3 model weights. Without this, the agent will return a "Model Not Found" error. Run this command to pull the 4B parameter version (the recommended "sweet spot" for technical accuracy and speed):
```bash
ollama pull gemma3
```
Make sure the ollama server is running (`ollama serve`).

### 🤖 Usage
Run the agent in interactive mode:
```bash
python lux_agent.py
```