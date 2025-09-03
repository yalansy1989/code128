import re
from io import BytesIO
import streamlit as st
from barcode import Code128
from barcode.writer import ImageWriter

st.set_page_config(page_title="مولّد Code128 مضبوط المقاس", page_icon="🔖", layout="centered")
st.title("🔖 مولّد Code-128 مضبوط على قياسات الطباعة")

# ---------- أدوات مساعدة ----------
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

def sanitize_ascii(s: str) -> str:
    """
    يحوّل الأرقام العربية إلى إنجليزية، ويزيل كل المحارف غير ASCII
    بما فيها علامات الاتجاه الخفية التي تسبب تكرارًا غريبًا في بعض الحقول.
    """
    s = s.translate(ARABIC_DIGITS)
    # حذف محارف تحكم واتجاه غير مرئية
    bidi = r"\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff"
    s = re.sub(f"[{bidi}]", "", s)
    # إبقاء ASCII فقط (أرقام/حروف/رموز مسموحة في Code128)
    s = "".join(ch for ch in s if ord(ch) < 128)
    return s.strip()

def inches_to_mm(x): return x * 25.4

def estimate_modules(n_chars: int) -> int:
    # تقريب شائع لرموز Code128: 11 وحدة لكل رمز + البداية + التحقق + التوقف (+2 إنهاء)
    return 11 * (n_chars + 3) + 2

def make_code128_png(data: str, width_in: float, height_in: float, dpi: int, quiet_mm: float):
    data = sanitize_ascii(data)
    if not data:
        raise ValueError("النص بعد التنقية فارغ.")

    width_mm  = inches_to_mm(width_in)
    height_mm = inches_to_mm(height_in)

    modules = estimate_modules(len(data))
    # حساب عرض أضيق شريط بالمليمتر بحيث يطابق عرض الصفحة المطلوب
    usable_mm = max(1e-6, width_mm - 2 * quiet_mm)
    module_width_mm = usable_mm / modules

    writer = ImageWriter()
    options = {
        "write_text": False,             # بدون رقم أسفل الكود
        "dpi": dpi,                      # الدقة الفعلية للملف
        "module_width": module_width_mm, # ← سر تطابق العرض
        "module_height": height_mm,      # ارتفاع الأشرطة (مم)
        "quiet_zone": quiet_mm,          # هامش صامت (مم)
        "background": "white",
        "foreground": "black",
    }

    barcode = Code128(data, writer=writer)
    buf = BytesIO()
    barcode.write(buf, options)  # PNG في الذاكرة
    buf.seek(0)
    return buf, data, module_width_mm

# ---------- واجهة ----------
with st.container(border=True):
    raw = st.text_input("أدخل الرقم/النص", "72626525252626625")
    colA, colB = st.columns(2)
    with colA:
        target_w_in = st.number_input("العرض المطلوب (إنش)", value=1.86, min_value=0.5, step=0.01)
        dpi = st.slider("الدقّة (DPI)", 300, 1200, 600, step=100)
    with colB:
        target_h_in = st.number_input("الارتفاع المطلوب (إنش)", value=0.28, min_value=0.2, step=0.01)
        quiet_mm = st.number_input("الهامش الصامت (مم لكل جانب)", value=2.0, min_value=0.0, step=0.25)

    # عرض النص بعد التنقية لمنع تكرار الأرقام عند اللصق
    clean = sanitize_ascii(raw)
    st.caption(f"النص بعد التنقية: `{clean}`")

    if st.button("إنشاء الباركود بالمقاس المحدّد"):
        try:
            png_buf, used_data, mw_mm = make_code128_png(
                clean, target_w_in, target_h_in, dpi, quiet_mm
            )
            st.image(png_buf, caption=f"Code128 @ {target_w_in:.2f}×{target_h_in:.2f} inch  |  mw≈{mw_mm:.3f} mm", use_container_width=True)
            st.download_button("⬇️ تحميل PNG", data=png_buf, file_name="code128.png", mime="image/png")
            st.success("تم إنشاء الملف بالمقاس المحدّد. اطبعه بنسبة 100% بدون ملاءمة للصفحة (no scale).")
        except Exception as e:
            st.error(f"تعذّر الإنشاء: {e}")
