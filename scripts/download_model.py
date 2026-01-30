#!/usr/bin/env python3
"""
Download GGUF model from HuggingFace for local inference.

Usage:
    python scripts/download_model.py
    python scripts/download_model.py --quantization Q8_0
"""
import os
import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def download_model(
    repo_id: str = "unsloth/DeepSeek-R1-Distill-Qwen-1.5B-GGUF",
    filename: str = None,
    quantization: str = "Q4_K_M",
    output_dir: str = "model"
):
    """
    Download a GGUF model from HuggingFace.
    
    Args:
        repo_id: HuggingFace repository ID
        filename: Specific filename to download (auto-generated if None)
        quantization: Quantization level (Q4_K_M, Q8_0, Q5_K_M, etc.)
        output_dir: Directory to save the model
    """
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("Installing huggingface_hub...")
        os.system(f"{sys.executable} -m pip install huggingface_hub")
        from huggingface_hub import hf_hub_download
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate filename if not provided
    if filename is None:
        # Common naming patterns for GGUF files
        filename = f"DeepSeek-R1-Distill-Qwen-1.5B-{quantization}.gguf"
    
    print(f"Downloading model from {repo_id}")
    print(f"  Filename: {filename}")
    print(f"  Quantization: {quantization}")
    print(f"  Output: {output_dir}/{filename}")
    print()
    
    try:
        # Download the model
        downloaded_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=output_dir,
            local_dir_use_symlinks=False
        )
        
        print(f"\n✅ Model downloaded successfully!")
        print(f"   Path: {downloaded_path}")
        print(f"\n📝 Update your config/llm.yaml:")
        print(f"   model_path: \"{output_dir}/{filename}\"")
        
        return downloaded_path
        
    except Exception as e:
        print(f"\n❌ Download failed: {e}")
        print("\nAvailable quantizations for DeepSeek-R1-Distill-Qwen-1.5B:")
        print("  - Q4_K_M (recommended, ~1GB)")
        print("  - Q5_K_M (~1.2GB)")
        print("  - Q8_0 (best quality, ~1.6GB)")
        print("  - Q2_K (smallest, ~0.6GB)")
        print("\nTry manually downloading from:")
        print(f"  https://huggingface.co/{repo_id}/tree/main")
        return None


def main():
    parser = argparse.ArgumentParser(description="Download GGUF model for local inference")
    parser.add_argument(
        "--repo",
        default="unsloth/DeepSeek-R1-Distill-Qwen-1.5B-GGUF",
        help="HuggingFace repository ID"
    )
    parser.add_argument(
        "--quantization", "-q",
        default="Q4_K_M",
        choices=["Q2_K", "Q3_K_S", "Q3_K_M", "Q4_K_S", "Q4_K_M", "Q5_K_S", "Q5_K_M", "Q6_K", "Q8_0"],
        help="Quantization level (default: Q4_K_M)"
    )
    parser.add_argument(
        "--output", "-o",
        default="models",
        help="Output directory (default: models)"
    )
    parser.add_argument(
        "--filename", "-f",
        default=None,
        help="Specific filename to download"
    )
    
    args = parser.parse_args()
    
    download_model(
        repo_id=args.repo,
        filename=args.filename,
        quantization=args.quantization,
        output_dir=args.output
    )


if __name__ == "__main__":
    main()
