# Quick GPU Setup - Windows

## TL;DR - Fix GPU in 3 Steps

### 1. Check Current Status
```cmd
python scripts/check_gpu_setup.py
```

### 2. Install CUDA Support for llama-cpp-python
```cmd
REM Make sure PyTorch CUDA is installed first:
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

REM Then reinstall llama-cpp-python WITH CUDA (takes 5-10 mins):
set CMAKE_ARGS=-DGGML_CUDA=on
pip install llama-cpp-python --force-reinstall --no-cache-dir
```

### 3. Verify & Run
```cmd
python scripts/check_gpu_setup.py
python backend/main.py
```

**Expected:** 
- ✓ CUDA GPU detected
- ✓ GPU layers: -1 (all on GPU)
- ✓ RTX shows 40-90% usage in Task Manager

---

## What's Wrong?

Your setup shows:
- ✓ **Config**: Correct (llama-cpp, GGUF model, n_gpu_layers=-1)
- ✓ **Model**: Exists (DeepSeek-R1-1.5B)
- ✗ **GPU**: Not being used (Intel UHD active instead of RTX)

**Cause:** `llama-cpp-python` compiled without CUDA support

---

## Why This Matters

| Aspect | Current (CPU) | After Fix (GPU) |
|--------|-------------|-----------------|
| Speed | 3-5 min/inference | 30-60 sec/inference |
| RTX Usage | 0% | 80%+ |
| CPU Usage | 100% | 20-30% |
| Faster by | - | **5-10x** |

---

## Commands for Different CUDA Versions

### CUDA 11.8 (Recommended - most compatible)
```cmd
set CMAKE_ARGS=-DGGML_CUDA=on
pip install llama-cpp-python --force-reinstall --no-cache-dir
```

### CUDA 12.x
```cmd
set CMAKE_ARGS=-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=all
pip install llama-cpp-python --force-reinstall --no-cache-dir
```

### If Stuck
```cmd
pip install --upgrade pip
pip install cmake
REM Then try the CMAKE_ARGS commands above
```

---

## Files to Check

| File | Purpose |
|------|---------|
| `config/llm.yaml` | LLM config (already correct) |
| `backend/utils/llm_client.py` | LocalLlamaClient (enhanced with GPU detection) |
| `scripts/check_gpu_setup.py` | Diagnostic tool (new) |
| `GPU_SETUP_GUIDE.md` | Full guide |

---

## Logs to Look For

After GPU fix, these should appear in logs:

```
INFO - CUDA GPU detected: NVIDIA GeForce RTX 4060 (8.00 GB)
INFO - GPU layer configuration: Using ALL layers on GPU
```

If you see:
```
WARNING - GPU layer configuration: CPU only (no GPU acceleration)
```

Then the fix didn't work - CUDA support wasn't compiled.

---

## One-Liner Fix (Copy & Paste)

```cmd
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118 && set CMAKE_ARGS=-DGGML_CUDA=on && pip install llama-cpp-python --force-reinstall --no-cache-dir && python scripts/check_gpu_setup.py
```

---

## Still Not Working?

1. Run: `python scripts/check_gpu_setup.py` - tells you what's wrong
2. Check CUDA: `python -c "import torch; print(torch.cuda.is_available())"`
3. Check build: `python -c "import llama_cpp; print(llama_cpp.__version__)"`
4. See GPU_SETUP_GUIDE.md for detailed troubleshooting
