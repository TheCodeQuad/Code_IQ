"""
GPU Analysis and Recommendation Script
Helps you determine optimal training parameters for your GPU
"""

import torch
import subprocess
import sys

def format_size(bytes_val):
    """Format bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024:
            return f"{bytes_val:.2f}{unit}"
        bytes_val /= 1024
    return f"{bytes_val:.2f}TB"

def get_gpu_info():
    """Get detailed GPU information"""
    if not torch.cuda.is_available():
        print("❌ ERROR: CUDA not available!")
        print("Make sure you have:")
        print("  - NVIDIA GPU")
        print("  - CUDA 11.8+ installed")
        print("  - PyTorch with CUDA support installed")
        return False
    
    num_gpus = torch.cuda.device_count()
    print(f"✅ GPUs found: {num_gpus}")
    print()
    
    total_memory = 0
    for i in range(num_gpus):
        props = torch.cuda.get_device_properties(i)
        memory = props.total_memory
        total_memory += memory
        
        print(f"GPU {i}: {props.name}")
        print(f"  Total Memory: {format_size(memory)}")
        print(f"  Compute Capability: {props.major}.{props.minor}")
        print()
    
    return total_memory

def get_recommendations(total_memory):
    """Get training recommendations based on GPU memory"""
    memory_gb = total_memory / (1024**3)
    
    print("="*60)
    print("TRAINING RECOMMENDATIONS")
    print("="*60)
    print()
    
    if memory_gb < 8:
        print("⚠️  WARNING: Less than 8GB VRAM detected")
        print("Training might be challenging. Consider:")
        print("  - Reducing dataset size significantly")
        print("  - Using smaller batch size")
        print("  - Reducing LoRA rank")
        config = {
            "train_split": "train[:0.25%]",
            "test_split": "test[:250]",
            "batch_size": 1,
            "gradient_accumulation_steps": 16,
            "lora_r": 4,
        }
    elif memory_gb < 12:
        print("✅ 8-12GB VRAM: Good for fine-tuning")
        print("Recommended configuration:")
        config = {
            "train_split": "train[:0.5%]",
            "test_split": "test[:500]",
            "batch_size": 1,
            "gradient_accumulation_steps": 8,
            "lora_r": 8,
        }
    elif memory_gb < 16:
        print("✅ 12-16GB VRAM: Great for fine-tuning")
        print("Recommended configuration:")
        config = {
            "train_split": "train[:1%]",
            "test_split": "test[:1000]",
            "batch_size": 2,
            "gradient_accumulation_steps": 4,
            "lora_r": 8,
        }
    elif memory_gb < 24:
        print("✅ 16-24GB VRAM: Excellent for fine-tuning")
        print("Recommended configuration:")
        config = {
            "train_split": "train[:2%]",
            "test_split": "test[:2000]",
            "batch_size": 4,
            "gradient_accumulation_steps": 2,
            "lora_r": 16,
        }
    else:
        print("✅ 24GB+ VRAM: Premium setup")
        print("Recommended configuration:")
        config = {
            "train_split": "train[:5%]",
            "test_split": "test[:5000]",
            "batch_size": 8,
            "gradient_accumulation_steps": 1,
            "lora_r": 16,
        }
    
    print()
    print(f"VRAM: {memory_gb:.2f}GB")
    print(f"Train Split: {config['train_split']}")
    print(f"Test Split: {config['test_split']}")
    print(f"Batch Size: {config['batch_size']}")
    print(f"Gradient Accumulation: {config['gradient_accumulation_steps']}")
    print(f"LoRA Rank: {config['lora_r']}")
    print()
    
    return config

def estimate_training_time(config, memory_gb):
    """Estimate training time"""
    print("="*60)
    print("ESTIMATED TRAINING TIME")
    print("="*60)
    print()
    
    # Rough estimates based on empirical data
    # These are for full fine-tuning with the given config
    time_per_epoch = {
        (0, 8): 4.0,      # <8GB: slow
        (8, 12): 2.5,     # 8-12GB: moderate
        (12, 16): 1.5,    # 12-16GB: good
        (16, 24): 1.0,    # 16-24GB: very good
        (24, 1000): 0.5,  # 24GB+: excellent
    }
    
    # Find matching range
    hours_per_epoch = 4.0
    for (min_mem, max_mem), hours in time_per_epoch.items():
        if min_mem <= memory_gb < max_mem:
            hours_per_epoch = hours
            break
    
    total_hours = hours_per_epoch * 3  # 3 epochs
    
    print(f"Per epoch: ~{hours_per_epoch:.1f} hours")
    print(f"3 epochs: ~{total_hours:.1f} hours ({total_hours/24:.1f} days)")
    print()
    print("Note: Actual time depends on:")
    print("  - Dataset download speed")
    print("  - GPU temperature/throttling")
    print("  - System load")
    print()

def check_pytorch_installation():
    """Check PyTorch installation details"""
    print("="*60)
    print("PYTORCH INFORMATION")
    print("="*60)
    print()
    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA version: {torch.version.cuda}")
    print(f"cuDNN version: {torch.backends.cudnn.version()}")
    print(f"cuDNN enabled: {torch.backends.cudnn.enabled}")
    print()
    
    # Try importing required libraries
    required_libs = [
        'transformers',
        'datasets',
        'peft',
        'bitsandbytes',
        'nltk',
        'rouge_score',
        'codebleu'
    ]
    
    print("Required libraries:")
    all_ok = True
    for lib in required_libs:
        try:
            mod = __import__(lib)
            version = getattr(mod, '__version__', 'unknown')
            print(f"  ✅ {lib}: {version}")
        except ImportError:
            print(f"  ❌ {lib}: NOT INSTALLED")
            all_ok = False
    
    print()
    if not all_ok:
        print("⚠️  Some libraries are missing. Run: pip install -r requirements.txt")
    
    return all_ok

def main():
    print()
    print("╔" + "="*58 + "╗")
    print("║" + " "*10 + "GPU Analysis & Configuration Tool" + " "*15 + "║")
    print("╚" + "="*58 + "╝")
    print()
    
    # Check PyTorch
    print("Checking PyTorch installation...")
    check_pytorch_installation()
    
    # Check GPU
    print("="*60)
    print("GPU INFORMATION")
    print("="*60)
    print()
    
    total_memory = get_gpu_info()
    if total_memory is False:
        print("\n❌ Setup failed. Please install CUDA and PyTorch correctly.")
        sys.exit(1)
    
    # Get recommendations
    config = get_recommendations(total_memory / (1024**3))
    
    # Estimate time
    estimate_training_time(config, total_memory / (1024**3))
    
    # Print summary
    print("="*60)
    print("NEXT STEPS")
    print("="*60)
    print()
    print("1. Update fine_tune_local_gpu.py with recommended settings:")
    print(f"   TRAIN_SPLIT = '{config['train_split']}'")
    print(f"   TEST_SPLIT = '{config['test_split']}'")
    print(f"   per_device_train_batch_size = {config['batch_size']}")
    print(f"   gradient_accumulation_steps = {config['gradient_accumulation_steps']}")
    print()
    print("2. Run: python scripts/fine_tune_local_gpu.py")
    print("3. Monitor with: nvidia-smi")
    print()

if __name__ == "__main__":
    main()
