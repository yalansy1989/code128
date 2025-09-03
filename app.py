# app.py
import re
from io import BytesIO
import streamlit as st
from barcode import Code128
from barcode.writer import ImageWriter

st.set_page_config(page_title="Code128 مضبوط المقاس", page_icon="🔖", layout="centered")
st.title("🔖 مولّد Code-128 مطابق لقياس جرير")

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
def sanitize_ascii(s: str) -> str:
    s = s.translate(ARABIC_DIGITS)
    bidi = r"\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff"
    s = re.sub(f"[{bidi}]", "", s)
    return "".join(ch for ch in s if ord(ch) < 128).strip()

def inches_to_mm(x): return x * 25.4

def render_png(data: str, dpi: int, module_width_mm: float, module_height_mm: float, quiet_mm: float):
    writer = ImageWriter()
    opts = {
        "write_text": False,
        "dpi": dpi,
        "module_width": module_width_mm,
        "module_height": module_height_mm,
        "quiet_zone": quiet_mm,
        "background": "white",
        "foreground": "black",
    }
    code = Code128(data, writer=writer)
    buf = BytesIO()
    code.write(buf, opts)
    buf.seek(0)
    return buf, writer, code, opts

def calc_total_width_mm(writer: ImageWriter, code_obj, opts) -> float:
    # تستخدم دالة المكتبة الداخلية لحساب الحجم الحقيقي بناءً على الترميز الفعلي
    w_mm, _ = writer.calculate_size(code_obj.get_fullcode(), opts["module_width"], opts["module_height"])
    # تضيف calculate_size الـ quiet zone تلقائياً
    return w_mm

def fit_width_mm(data: str, target_width_mm: float, dpi: int, height_mm: float, quiet_mm: float,
                 mw_low=0.02, mw_high=0.8, tol=0.02):
    """
    نضبط module_width بالـ binary search حتى يصبح العرض الكلي ≈ target_width_mm
    tol = سماحية الخطأ بالملّيمتر (0.02mm كافية للطباعة).
    """
    data = sanitize_ascii(data)
    if not data:
        raise ValueError("النص بعد التنقية فارغ.")

    # حدود البحث
    low, high = mw_low, mw_high
    best_mw, best_err = None, 1e9

    writer = ImageWriter()
    code = Code128(data, writer=writer)
    while high - low > 1e-4:
        mid = (low + high) / 2
        opts = {
            "write_text": False,
            "dpi": dpi,
            "module_width": mid,
            "module_height": height_mm,
            "quiet_zone": quiet_mm,
            "background": "white",
            "foreground": "black",
        }
        w_mm, _ = writer.calculate_size(code.get_fullcode(), mid, height_mm)
        err = w_mm - target_width_mm
        if abs(err) < best_err:
            best_err, best_mw = abs(err), mid
        if err > 0:
            high = mid
        else:
            low = mid
        if abs(err) <= tol:
            best_mw = mid
            break
    # الآن نرسم بالـ module_width المثالي
    png_buf, _, _, _ = render_png(data, dpi, best_mw, height_mm, quiet_mm)
    return png_buf, best_mw

# -------- واجهة --------
raw = st.text_input("النص / الرقم", "72626525252626625")
col1, col2 = st.columns(2)
with col1:
    width_in  = st.number_input("العرض المستهدف (إنش)", value=1.86, min_value=0.5, step=0.01)
    dpi       = st.slider("الدقّة (DPI)", 300, 1200, 600, step=100)
with col2:
    height_in = st.number_input("الارتفاع (إنش)", value=0.28, min_value=0.2, step=0.01)
    quiet_mm  = st.number_input("الهامش الصامت لكل جانب (مم)", value=2.0, min_value=0.0, step=0.25)

if st.button("إنشاء مطابق لجرير"):
    try:
        target_w_mm = inches_to_mm(width_in)
        height_mm   = inches_to_mm(height_in)
        buf, mw_used = fit_width_mm(raw, target_w_mm, dpi, height_mm, quiet_mm)
        st.image(buf, caption=f"عرض مضبوط ≈ {width_in:.2f}″ | mw≈{mw_used:.3f} mm", use_container_width=True)
        st.download_button("⬇️ تحميل PNG", data=buf, file_name="code128.png", mime="image/png")
        st.info("ملاحظة: اطبع بنسبة 100% دون 'Fit to page'.")
    except Exception as e:
        st.error(f"خطأ: {e}")
