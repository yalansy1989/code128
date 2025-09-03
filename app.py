# -*- coding: utf-8 -*-
import re
from io import BytesIO
import streamlit as st
from barcode import Code128
from barcode.writer import ImageWriter

st.set_page_config(page_title="مولّد Code-128", page_icon="🔖", layout="centered")
st.title("🔖 مولّد Code-128 تلقائي")

# تنظيف النص من أرقام عربية أو محارف غير ASCII
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
def sanitize(s: str) -> str:
    s = (s or "").translate(ARABIC_DIGITS)
    s = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]", "", s)
    return "".join(ch for ch in s if ord(ch) < 128).strip()

def make_png_bytes(data: str) -> bytes:
    writer = ImageWriter()
    opts = {
        "write_text": False,  # بدون الرقم أسفل الباركود
        "dpi": 300,           # دقة متوسطة (تلقائية)
        "background": "white",
        "foreground": "black",
    }
    code = Code128(data, writer=writer)
    buf = BytesIO()
    code.write(buf, opts)
    return buf.getvalue()

# واجهة
num = st.text_input("أدخل الرقم/النص")
if st.button("إنشاء الكود"):
    clean = sanitize(num)
    if not clean:
        st.error("أدخل رقمًا/نصًا صالحًا.")
    else:
        png_bytes = make_png_bytes(clean)
        st.image(png_bytes, caption="Code-128", use_container_width=True)
        st.download_button("⬇️ تحميل PNG", png_bytes, file_name="code128.png", mime="image/png")
