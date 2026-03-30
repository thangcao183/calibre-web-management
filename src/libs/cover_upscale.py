import os
import io
import requests
from pathlib import Path
from PIL import Image, ImageFilter, ImageEnhance
import numpy as np

def load_image(input_data):
    """
    Load an image from a file path, URL, or buffer into a PIL Image (RGB).
    """
    try:
        if isinstance(input_data, str):  # File path or URL
            if input_data.startswith(("http://", "https://")):
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": input_data,
                    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                }
                response = requests.get(input_data, timeout=10, headers=headers)
                response.raise_for_status()
                img = Image.open(io.BytesIO(response.content)).convert("RGB")
            else:
                img = Image.open(input_data).convert("RGB")
        elif isinstance(input_data, bytes):
            img = Image.open(io.BytesIO(input_data)).convert("RGB")
        elif isinstance(input_data, io.BytesIO):
            input_data.seek(0)
            img = Image.open(input_data).convert("RGB")
        else:
            raise ValueError("Unsupported input type.")
        return img
    except Exception as e:
        print(f"Error loading image: {e}")
        return None

def upscale_with_realesrgan(input_data, scale=4):
    """
    Upscale an image using RealESRGAN via Spandrel (PyTorch).
    """
    img = load_image(input_data)
    if img is None:
        return None

    # Do not upscale if the image is already large enough
    if img.width >= 600:
        print("Image width is >= 600px. Returning original image.")
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="JPEG")
        return img_buffer.getvalue()

    # Pre-trained RealESRGAN model path
    current_dir = Path(__file__).resolve().parent
    model_name = "4x-UltraSharp.pth"
    model_path = current_dir / "models" / model_name

    # Only load from local file, do not download
    if not os.path.exists(model_path):
        print(f"Warning: Model file {model_path} not found. Skipping upscale.")
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="JPEG")
        return img_buffer.getvalue()

    try:
        import torch
        from spandrel import ModelLoader
        
        # Load model using Spandrel
        model = ModelLoader().load_from_file(str(model_path)).eval()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = model.to(device)
        
        # Convert PIL to PyTorch Tensor [1, C, H, W]
        img_np = np.array(img).astype(np.float32) / 255.0
        img_t = torch.from_numpy(img_np).permute(2, 0, 1).unsqueeze(0).to(device)
        
        # Upscale
        with torch.no_grad():
            output_t = model(img_t)
            
        # Convert back
        output_np = output_t.squeeze().permute(1, 2, 0).cpu().numpy().clip(0, 1) * 255
        output_img = Image.fromarray(output_np.astype(np.uint8))
        
        img_buffer = io.BytesIO()
        output_img.save(img_buffer, format="JPEG", quality=95)
        return img_buffer.getvalue()
        
    except Exception as e:
        print(f"Error during RealESRGAN PyTorch upscaling: {e}")
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="JPEG")
        return img_buffer.getvalue()