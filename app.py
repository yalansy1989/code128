# -*- coding: utf-8 -*-
import re
from io import BytesIO
from PIL import Image
import streamlit as st
from barcode import Code128
from barcode.writer import ImageWriter

# ===== مقاس جرير الافتراضي =====
WIDTH_IN  = 1.86   # العرض بالبوصة
HEIGHT_IN = 0.28   # الارتفاع بالبوصة
DPI       = 600    # دقة الطباعة (غيّرها إذا لزم)
QUIET_MM  = 2.0    # الهامش الصامت لكل جانب بالملّيمتر
# ==============================

def inches_to_mm(x): return float(x) * 25.4
def px_from_in(inches, dpi): return int(round(float(inches) * int(dpi)))

# تنظيف النص (حل تكرار الأرقام عند اللصق)
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
def sanitize(s: str) -> str:
    s = (s or "").translate(ARABIC_DIGITS)
    s = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]", "", s)
    return "".join(ch for ch in s if ord(ch) < 128).strip()

def render_barcode_png_bytes(data: str) -> bytes:
    """نولّد الباركود PNG بدون نص سفلي وبـ DPI محدد."""
    writer = ImageWriter()
    opts = {
        "write_text": False,
        "dpi": int(DPI),
        "module_height": inches_to_mm(HEIGHT_IN),  # ارتفاع الأشرطة (مم)
        "quiet_zone": float(QUIET_MM),             # هامش صامت (مم)
        "background": "white",
        "foreground": "black",
        # ملاحظة: نترك module_width للمكتبة (اختيار مناسب)،
        # وسنعالج المقاس النهائي بالـ padding بدل التمديد.
    }
    code = Code128(data, writer=writer)
    buf = BytesIO()
    code.write(buf, opts)
    return buf.getvalue()

def pad_to_target_size(png_bytes: bytes, target_w_px: int, target_h_px: int) -> bytes:
    """نضيف Padding أبيض للوصول إلى الأبعاد المطلوبة دون تغيير الأشرطة."""
    with Image.open(BytesIO(png_bytes)) as im:
        cur_w, cur_h = im.size
        # لا نُغيّر الحجم (لا resize) — فقط نعمل لوحة أكبر ونضع الصورة في الوسط
        canvas = Image.new("RGB", (target_w_px, target_h_px), "white")
        off_x = max(0, (target_w_px - cur_w) // 2)
        off_y = max(0, (target_h_px - cur_h) // 2)
        canvas.paste(im, (off_x, off_y))
        out = BytesIO()
        canvas.save(out, format="PNG", dpi=(DPI, DPI))
        return out.getvalue()

# واجهة مبسطة: إدخال رقم + زر واحد
st.set_page_config(page_title="Code-128 Jarir Size", page_icon="🔖", layout="centered")
st.title("🔖 مولّد Code-128 مطابق لمقاس جرير")

num = st.text_input("أدخل الرقم/النص")
if st.button("إنشاء الكود"):
    clean = sanitize(num)
    if not clean:
        st.error("أدخل رقمًا/نصًا صالحًا.")
    else:
        try:
            # 1) توليد الباركود بالحجم الطبيعي
            raw_png = render_barcode_png_bytes(clean)
            # 2) حساب أبعاد جرير بالبكسل
            w_px = px_from_in(WIDTH_IN, DPI)
            h_px = px_from_in(HEIGHT_IN, DPI)
            # 3) إضافة padding لتطابق الأبعاد تمامًا
            final_png = pad_to_target_size(raw_png, w_px, h_px)

            st.image(final_png, caption=f"{WIDTH_IN}×{HEIGHT_IN} inch @ {DPI} DPI", use_container_width=True)
            st.download_button("⬇️ تحميل PNG", final_png, file_name="code128_jarir.png", mime="image/png")
            st.success("جاهز للطباعة. في برنامج الطباعة: Scale = 100%، ألغِ Fit to page.")
        except Exception as e:
            st.error(f"تعذّر الإنشاء: {e}")
