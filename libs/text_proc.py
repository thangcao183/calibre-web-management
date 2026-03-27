import re
import unicodedata
def remove_accents_and_special_chars(text: str) -> str:
    # Bỏ dấu tiếng Việt
    text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    
    # Loại bỏ ký tự đặc biệt, chỉ giữ lại chữ cái và số
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    
    # Chuẩn hóa khoảng trắng
    text = re.sub(r'\s+', ' ', text).strip()

    return text

def clean_json_string(json_str):
    json_str = json_str.split("window.bookData = ", 1)[-1].strip()
    # Thay thế nháy đơn bằng nháy kép nếu có
    json_str = json_str.replace("'", '"')

    # Xóa dấu phẩy cuối cùng trước dấu đóng ngoặc `}`
    json_str = re.sub(r",\s*}", "}", json_str)
    json_str = re.sub(r",\s*]", "]", json_str)

    return json_str

def smart_punctuation(text: str) -> str:
    """
    Chuẩn hóa dấu câu trong văn bản theo chuẩn typographic.
    """
    if not text:
        return ""

    # Chuyển đổi dấu nháy đơn và đôi thành kiểu cong
    text = re.sub(r'(?<!\w)"(.*?)"', r'“\1”', text)  # Dấu nháy kép
    text = re.sub(r"(?<!\w)'(.*?)'", r'<i>‘\1’</i>', text)  # Dấu nháy đơn

    # Thay thế ba dấu chấm thành dấu chấm lửng
    text = text.replace("...", "…")

    # Thay thế hai dấu gạch ngang thành em-dash
    text = re.sub(r'\s*--\s*', " — ", text)

    # Chuẩn hóa khoảng cách trước dấu câu
    text = re.sub(r'\s+([,.!?;:])', r'\1', text)  # Xóa khoảng trắng trước dấu câu
    text = re.sub(r'([(\[{])\s+', r'\1', text)  # Xóa khoảng trắng sau dấu mở ngoặc
    text = re.sub(r'\s+([)\]}])', r'\1', text)  # Xóa khoảng trắng trước dấu đóng ngoặc

    return text.strip()