# -*- coding: utf-8 -*-
import re
from io import BytesIO
import streamlit as st
from barcode import Code128
from barcode.writer import ImageWriter

st.set_page_config(page_title="مولّد Code-128 (مطابق جرير)", page_icon="🔖", layout="centered")
st.markdown("<h1 style='text-align:right'>مولّد <b>Code-128</b> مطابق لقياس جرير</h1>", unsafe_allow_html=True)

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

def sanitize_ascii(s: str) -> str:
    s = s.translate(ARABIC_DIGITS)
    bidi = r"\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff"
    s = re.sub(f"[{bidi}]", "", s)
    s = "".join(ch for ch in s if ord(ch) < 128)
    return s.strip()

def inches_to_mm(x: float) -> float:
    return x * 25.4

def render_png(data: str, dpi: int, module_width_mm: float, module_height_mm: float, quiet_mm: float) -> BytesIO:
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
    return buf

def fit_width_mm(data: str, target_width_mm: float, dpi: int, height_mm: float, quiet_mm: float,
                 mw_low=0.02, mw_high=0.8, tol=0.02):
    data = sanitize_ascii(data)
    if not data:
        raise ValueError("النص بعد التنقية فارغ.")

    writer = ImageWriter()
    code = Code128(data, writer=writer)

    low, high = mw_low, mw_high
    best_mw, best_err = None, 1e9

    while high - low > 1e-4:
        mid = (low + high) / 2.0
        # حساب العرض الحقيقي بدون quiet
        fullcode = code.get_fullcode()
        total_w_mm, _ = writer.calculate_size(fullcode, mid)
        # نضيف الهامش يمين + يسار
        total_w_mm += quiet_mm * 2

        err = total_w_mm - target_width_mm

        if abs(err) < best_err:
            best_err, best_mw = abs(err), mid

        if err > 0:
            high = mid
        else:
            low = mid

        if abs(err) <= tol:
            best_mw = mid
            break

    png_buf = render_png(data, dpi, best_mw, height_mm, quiet_mm)
    return png_buf, best_mw, data

# ---- الواجهة ----
with st.container(border=True):
    raw = st.text_input("النص / الرقم", "72626525252626625")

    col1, col2 = st.columns(2)
    with col1:
        width_in  = st.number_input("العرض المستهدف (إنش)", value=1.86, min_value=0.50, step=0.01)
        dpi       = st.slider("الدقّة (DPI)", min_value=300, max_value=1200, value=600, step=100)
    with col2:
        height_in = st.number_input("الارتفاع (إنش)", value=0.28, min_value=0.20, step=0.01)
        quiet_mm  = st.number_input("الهامش الصامت لكل جانب (مم)", value=2.0, min_value=0.0, step=0.25)

    clean = sanitize_ascii(raw)
    st.caption(f"النص بعد التنقية: `{clean}`")

    if st.button("إنشاء الكود"):
        try:
            target_w_mm = inches_to_mm(width_in)
            height_mm   = inches_to_mm(height_in)

            png_buf, mw_used, used_data = fit_width_mm(
                clean, target_w_mm, dpi, height_mm, quiet_mm
            )

            st.image(png_buf, caption=f"عرض مضبوط ≈ {width_in:.2f}″ | ارتفاع ≈ {height_in:.2f}″ | mw≈{mw_used:.3f} مم", use_container_width=True)
            st.download_button("⬇️ تحميل PNG", data=png_buf, file_name="code128.png", mime="image/png")

            st.success("جاهز للطباعة. تأكد أن إعداد الطابعة على 100% بدون Fit to page.")
        except Exception as e:
            st.error(f"تعذّر الإنشاء: {e}")
