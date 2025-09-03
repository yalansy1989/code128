# -*- coding: utf-8 -*-
import re
from io import BytesIO
from PIL import Image
import streamlit as st
from barcode import Code128
from barcode.writer import ImageWriter

# ===== مقاسات جرير =====
WIDTH_IN  = 1.86   # العرض بالبوصة
HEIGHT_IN = 0.28   # الارتفاع بالبوصة
DPI       = 600    # الدقة
QUIET_MM  = 0.0    # بدون هامش صامت خارجي
# ======================

def inches_to_mm(x): return float(x) * 25.4
def px_from_in(inches, dpi): return int(round(float(inches) * int(dpi)))

# تنظيف النص
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
def sanitize(s: str) -> str:
    s = (s or "").translate(ARABIC_DIGITS)
    s = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]", "", s)
    return "".join(ch for ch in s if ord(ch) < 128).strip()

def render_barcode_png_bytes(data: str) -> bytes:
    """إنشاء باركود PNG خام من المكتبة"""
    writer = ImageWriter()
    opts = {
        "write_text": False,
        "dpi": int(DPI),
        "module_height": inches_to_mm(HEIGHT_IN),  # ارتفاع أشرطة كـ mm
        "quiet_zone": QUIET_MM,
        "background": "white",
        "foreground": "black",
    }
    code = Code128(data, writer=writer)
    buf = BytesIO()
    code.write(buf, opts)
    return buf.getvalue()

def resize_to_exact(png_bytes: bytes, target_w_px: int, target_h_px: int) -> bytes:
    """إعادة تحجيم الباركود ليملىء الصورة بالكامل"""
    with Image.open(BytesIO(png_bytes)) as im:
        resized = im.resize((target_w_px, target_h_px), Image.NEAREST)
        out = BytesIO()
        resized.save(out, format="PNG", dpi=(DPI, DPI))
        return out.getvalue()

# واجهة
st.set_page_config(page_title="Code-128 Jarir", page_icon="🔖", layout="centered")
st.title("🔖 مولّد Code-128")

num = st.text_input("أدخل الرقم/النص")
if st.button("إنشاء الكود"):
    clean = sanitize(num)
    if not clean:
        st.error("أدخل رقمًا/نصًا صالحًا.")
    else:
        try:
            raw_png = render_barcode_png_bytes(clean)
            # أبعاد الهدف بالبكسل
            w_px = px_from_in(WIDTH_IN, DPI)
            h_px = px_from_in(HEIGHT_IN, DPI)
            final_png = resize_to_exact(raw_png, w_px, h_px)

            st.image(final_png, caption=f"{WIDTH_IN}×{HEIGHT_IN} inch @ {DPI} DPI", use_container_width=True)
            st.download_button("⬇️ تحميل PNG", final_png, file_name="code128.png", mime="image/png")
            st.success("الكود يملأ الصورة بالكامل. اطبع بنسبة 100% بدون Fit to page.")
        except Exception as e:
            st.error(f"تعذّر الإنشاء: {e}")

