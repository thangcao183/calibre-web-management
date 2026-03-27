import io
from libs.cover_upscale import upscale_with_realesrgan

def main():
    # Điền URL hoặc đường dẫn file ảnh gốc trên máy bạn vào đây
    input_image = "https://www.nae.vn/ttv/ttv/public/images/story/b460f29063fe75f58b377574bcfb77a288c8416240f25358c94d536351eb9cde.jpg"
    
    print("="*50)
    print(f"Đang tiến hành Upscale ảnh từ: {input_image}")
    print("Lưu ý: Lần chạy đầu tiên sẽ mất thời gian tải Model nặng ~180MB.")
    print("Và mất khoảng 15-30 giây để xử lý tính toán kiến trúc HAT trên CPU...")
    print("="*50)

    # Giao ảnh cho file thư viện cover_upscale xử lý (Nó sẽ tự tải ảnh + upscale)
    upscaled_bytes = upscale_with_realesrgan(input_image)
    
    if upscaled_bytes:
        out_path = "test_hat_upscaled.jpg"
        # Ghi bytes dữ liệu đầu ra thành file ảnh jpg
        with open(out_path, "wb") as f:
            f.write(upscaled_bytes)
        print(f"\n✅ Hoàn tất cực chuẩn! Ảnh kết quả đã được lưu thành file '{out_path}'.")
        print("Mở file đó lên và zoom vào từng nét chữ để check độ chi tiết nhé!")
    else:
        print("\n❌ Upscale thất bại, kiểm tra lại lỗi trên console.")

if __name__ == "__main__":
    main()
