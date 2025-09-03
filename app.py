# -*- coding: utf-8 -*-
import re
from io import BytesIO
import streamlit as st
from PIL import Image
from barcode import Code128
from barcode.writer import ImageWriter

# إعداد الصفحة
st.set_page_config(page_title="مولّد Code-128 (مطابق جرير)", page_icon="🔖", layout="centered")
st.markdown("<h1 style='text-align:right'>مولّد <b>Code-128</b> مطابق لقياس جرير</h1>", unsafe_allow_html=True)

# ---------- Utilities ----------
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

def sanitize_ascii(s: str) -> str:
    s = (s or "").translate(ARABIC_DIGITS)
    bidi = r"\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff"
    s = re.sub(f"[{bidi}]", "", s)
    s = "".join(ch for ch in s if ord(ch) < 128)
    return s.strip()

def fnum(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)

def inches_to_mm(x) -> float:
    return fnum(x) * 25.4

def render_png_bytes(data: str, dpi, module_width_mm, module_height_mm, quiet_mm) -> bytes:
    """يرسم الباركود ويرجع PNG bytes."""
    writer = ImageWriter()
    opts = {
        "write_text": False,
        "dpi": int(fnum(dpi)),
        "module_width": fnum(module_width_mm),
        "module_height": fnum(module_height_mm),
        "quiet_zone": fnum(quiet_mm),
        "background": "white",
        "foreground": "black",
    }
    code = Code128(data, writer=writer)
    buf = BytesIO()
    code.write(buf, opts)  # PNG
    return buf.getvalue()

def measure_width_mm_via_render(data: str, dpi, module_width_mm, module_height_mm, quiet_mm) -> float:
    """نقيس العرض الحقيقي عبر فتح الصورة وقراءة عدد البكسلات."""
    png_bytes = render_png_bytes(data, dpi, module_width_mm, module_height_mm, quiet_mm)
    with Image.open(BytesIO(png_bytes)) as im:
        px_w = im.size[0]
    # تحويل بكسل -> إنش -> مم
    return (px_w / fnum(dpi)) * 25.4

def fit_width_mm(data: str, target_width_mm, dpi, height_mm, quiet_mm,
                 mw_low=0.01, mw_high=1.00, tol_mm=0.02, max_iter=40):
    """
    نعدّل module_width بالـ binary search مع قياس فعلي بالصورة حتى يطابق العرض المطلوب.
    """
    data = sanitize_ascii(data)
    if not data:
        raise ValueError("النص بعد التنقية فارغ.")

    target = fnum(target_width_mm)
    low, high = fnum(mw_low), fnum(mw_high)
    best_mw, best_err = None, 1e9

    for _ in range(max_iter):
        mid = (low + high) / 2.0
        actual_mm = measure_width_mm_via_render(data, dpi, mid, height_mm, quiet_mm)
        err = actual_mm - target

        if abs(err) < best_err:
            best_err, best_mw = abs(err), mid

        if abs(err) <= fnum(tol_mm):
            best_mw = mid
            break

        if err > 0:
            high = mid      # الصورة أعرض من المطلوب → صغّر module_width
        else:
            low = mid       # الصورة أضيق من المطلوب → كبّر module_width

        if (high - low) < 1e-5:
            break

    # إنشاء الصورة النهائية بالعرض المضبوط
    png_bytes = render_png_bytes(data, dpi, best_mw, height_mm, quiet_mm)
    return png_bytes, best_mw, data

# ---------- UI ----------
with st.container(border=True):
    raw = st.text_input("النص / الرقم", "72626525252626625")

    col1, col2 = st.columns(2)
    with col1:
        width_in  = st.number_input("العرض المستهدف (إنش)", value=1.86, min_value=0.50, step=0.01, format="%.2f")
        dpi       = st.slider("الدقّة (DPI)", min_value=300, max_value=1200, value=600, step=100)
    with col2:
        height_in = st.number_input("الارتفاع (إنش)", value=0.28, min_value=0.20, step=0.01, format="%.2f")
        quiet_mm  = st.number_input("الهامش الصامت لكل جانب (مم)", value=2.0, min_value=0.0, step=0.25, format="%.2f")

    clean = sanitize_ascii(raw)
    st.caption(f"النص بعد التنقية: <code>{clean}</code>", unsafe_allow_html=True)

    if st.button("إنشاء الكود"):
        try:
            target_w_mm = inches_to_mm(width_in)
            height_mm   = inches_to_mm(height_in)

            png_bytes, mw_used, used_data = fit_width_mm(
                clean, target_w_mm, dpi, height_mm, quiet_mm
            )

            # أبعاد البكسل المتوقعة (للتأكد في الطابعة)
            px_w = int(round((target_w_mm / 25.4) * fnum(dpi)))
            px_h = int(round((height_mm   / 25.4) * fnum(dpi)))

            st.image(png_bytes, caption=f"عرض مضبوط ≈ {fnum(width_in):.2f}″ | ارتفاع ≈ {fnum(height_in):.2f}″ | mw≈{fnum(mw_used):.3f} مم", use_container_width=True)
            st.download_button("⬇️ تحميل PNG", data=png_bytes, file_name="code128.png", mime="image/png")
            st.success(f"جاهز للطباعة 100% بدون Fit to page. الأبعاد عند {dpi} DPI ≈ {px_w}×{px_h} بكسل.")
        except Exception as e:
            st.error(f"تعذّر الإنشاء: {e}")
