to run the project 
backend:
set PYTHONPATH=%CD%\backend
 
frontend:
cd frontend
npm run dev

---

## 🚀 Setup & Installation

### Prerequisites

- Python 3.11
- Git
- (Optional) OpenAI API key or local LLM (Ollama)

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Code_IQ

2.**create virtual environment**
conda create -n code_iq
conda activate code_iq

3.**Install dependencies**
pip install -r requirements.txt

4.**Setup Local LLM (Option A: Direct llama-cpp-python - Recommended for GPU)**

For direct local LLM inference with GPU acceleration:

**Step 1: Install llama-cpp-python with GPU support**
```powershell
# For NVIDIA CUDA GPU (RTX, GTX, etc.)
pip install llama-cpp-python --upgrade

# If wheel build fails (missing C++ compiler), use conda instead:
conda install -c conda-forge llama-cpp-python -y
```

**Step 2: Download GGUF model**
Download from HuggingFace and save to `models/` folder:
https://huggingface.co/unsloth/DeepSeek-R1-Distill-Qwen-1.5B-GGUF

Or download via Python:
```python
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id="unsloth/DeepSeek-R1-Distill-Qwen-1.5B-GGUF",
    filename="DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf",
    local_dir="models"
)
```

**Step 3: Verify CUDA Setup**
```powershell
# Check NVIDIA GPU availability
nvidia-smi

# Verify in Python
python -c "from llama_cpp import Llama; print('llama-cpp-python installed!')"
```

**Step 4: Test local inference**
```powershell
python test/local_llm.py
```

Configuration in `config/llm.yaml`:
```yaml
local:
  enabled: true
  mode: "llama_cpp"
  model_path: "models/DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf"
  n_ctx: 8192
  n_gpu_layers: -1  # All layers on GPU
  n_threads: null   # Auto-detect
```

**Troubleshooting wheel build errors:**
If you get "No CMAKE_C_COMPILER could be found" error:
1. Option 1 (Recommended): Use conda pre-built wheels
   ```powershell
   conda install -c conda-forge llama-cpp-python
   ```
2. Option 2: Install Visual Studio Build Tools with C++ workload
   - Download from: https://visualstudio.microsoft.com/downloads/
   - Select "Desktop development with C++"
   - Restart terminal after install

---

5.**Setup Ollama (Option B: Alternative HTTP-based)** 
Minimal setup (10 minutes)
1️⃣ Install Ollama

https://ollama.com/download/windows

2️⃣ Pull a model (do this once)
ollama pull qwen2.5:7b


5.**to run the project** 
backend:
set PYTHONPATH=%CD%\backend
python -m uvicorn backend.app:app --reload
 
frontend:
cd frontend
npm run dev



conda install -c conda-forge llama-cpp-python -y

<!-- D:\BIA6\Code_IQ -->

