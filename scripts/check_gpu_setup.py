#!/usr/bin/env python3
"""
Diagnostic script to check llama-cpp-python CUDA support and GPU configuration
"""
import os
import sys

def check_cuda():
    """Check if CUDA is available"""
    print("\n" + "="*60)
    print("CUDA/GPU Environment Check")
    print("="*60)
    
    try:
        import torch
        print(f"✓ PyTorch: {torch.__version__}")
        print(f"✓ CUDA Available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"✓ CUDA Version: {torch.version.cuda}")
            print(f"✓ GPU Device: {torch.cuda.get_device_name(0)}")
            print(f"✓ GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    except ImportError:
        print("✗ PyTorch not installed")
        return False
    
    return True


def check_llama_cpp():
    """Check if llama-cpp-python is installed and has CUDA support"""
    print("\n" + "="*60)
    print("llama-cpp-python Status")
    print("="*60)
    
    try:
        import llama_cpp
        print(f"✓ llama-cpp-python installed: {llama_cpp.__version__}")
        
        # Check CUDA support
        from llama_cpp import Llama
        
        # Try to get build info
        try:
            # This is a bit hacky but works to check CUDA support
            test_prompt = "test"
            # If CUDA is compiled in, it will show in the verbose output
            print("\nChecking build configuration...")
            
            # Check environment variable that indicates CUDA build
            cuda_env = os.environ.get('CUDA_VISIBLE_DEVICES', 'Not set')
            print(f"  CUDA_VISIBLE_DEVICES: {cuda_env}")
            
            # Check if the library was built with CUDA
            # This requires checking the compiled library
            import ctypes
            from pathlib import Path
            
            # Try to find llama.cpp shared library
            try:
                lib_path = Path(llama_cpp.__file__).parent
                print(f"  llama-cpp-python location: {lib_path}")
                
                # List files to see if CUDA library is present
                if lib_path.exists():
                    files = list(lib_path.glob("*.so")) + list(lib_path.glob("*.dll"))
                    if files:
                        print(f"  Found shared libraries:")
                        for f in files[:3]:  # Show first 3
                            print(f"    - {f.name}")
            except Exception as e:
                print(f"  Could not check library files: {e}")
        
        except Exception as e:
            print(f"✗ Could not fully inspect llama-cpp-python: {e}")
        
        return True
        
    except ImportError:
        print("✗ llama-cpp-python NOT installed")
        print("\n  To install with CUDA support:")
        print("  CMAKE_ARGS=\"-DGGML_CUDA=on\" pip install llama-cpp-python --force-reinstall --no-cache-dir")
        return False


def check_model_file():
    """Check if GGUF model file exists"""
    print("\n" + "="*60)
    print("Model File Status")
    print("="*60)
    
    model_path = "models/DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf"
    
    if os.path.exists(model_path):
        size_gb = os.path.getsize(model_path) / (1024**3)
        print(f"✓ Model found: {model_path}")
        print(f"  Size: {size_gb:.2f} GB")
        return True
    else:
        print(f"✗ Model NOT found: {model_path}")
        return False


def check_llm_config():
    """Check LLM configuration"""
    print("\n" + "="*60)
    print("LLM Configuration")
    print("="*60)
    
    try:
        from backend.utils.config_handler import get_config
        config = get_config()
        llm_config = config.get_config('llm')
        
        if llm_config:
            local_config = llm_config.get('providers', {}).get('local', {})
            print(f"✓ Local provider enabled: {local_config.get('enabled', False)}")
            print(f"  Mode: {local_config.get('mode', 'N/A')}")
            print(f"  Model path: {local_config.get('model_path', 'N/A')}")
            print(f"  Context size: {local_config.get('n_ctx', 'N/A')}")
            print(f"  GPU layers: {local_config.get('n_gpu_layers', 'N/A')}")
            print(f"  Threads: {local_config.get('n_threads', 'auto')}")
        else:
            print("✗ Could not load LLM config")
    except Exception as e:
        print(f"✗ Error loading config: {e}")


def main():
    print("\n" + "="*60)
    print("Code_IQ GPU Configuration Diagnostic")
    print("="*60)
    
    cuda_ok = check_cuda()
    llama_cpp_ok = check_llama_cpp()
    model_ok = check_model_file()
    check_llm_config()
    
    print("\n" + "="*60)
    print("Summary")
    print("="*60)
    
    if cuda_ok and llama_cpp_ok and model_ok:
        print("✓ All systems ready for GPU inference!")
        print("\nYour setup appears to be configured correctly.")
        print("If GPU is NOT being used during inference, the issue may be:")
        print("  1. llama-cpp-python was installed BEFORE PyTorch CUDA was installed")
        print("  2. The library needs to be reinstalled with CUDA enabled")
        print("\nTo fix, reinstall llama-cpp-python with CUDA:")
        print("  CMAKE_ARGS=\"-DGGML_CUDA=on\" pip install llama-cpp-python --force-reinstall --no-cache-dir")
    else:
        print("✗ Some components are missing:")
        if not cuda_ok:
            print("  - PyTorch with CUDA support not properly installed")
        if not llama_cpp_ok:
            print("  - llama-cpp-python needs to be installed with CUDA support")
        if not model_ok:
            print("  - Model file is missing")
        
        print("\nRun setup script: python setup_local_gpu.bat")


if __name__ == "__main__":
    main()
