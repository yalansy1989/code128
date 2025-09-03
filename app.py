# -*- coding: utf-8 -*-
import re
from io import BytesIO
import streamlit as st
from barcode import Code128
from barcode.writer import ImageWriter

st.set_page_config(page_title="مولّد Code-128 (مطابق جرير)", page_icon="🔖", layout="centered")
st.markdown("<h1 style='text-align:right'>مولّد <b>Code-128</b> مطابق لقياس جرير</h1>", unsafe_allow_html=True)

# ---------- Utilities ----------
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

def sanitize_ascii(s: str) -> str:
    s = (s or "").translate(ARABIC_DIGITS)
    # remove bidi/hidden control chars that cause duplicated digits
    bidi = r"\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff"
    s = re.sub(f"[{bidi}]", "", s)
    s = "".join(ch for ch in s if ord(ch) < 128)
    return s.strip()

def fnum(x, default=0.0) -> float:
    """coerce any value to float safely."""
    try:
        return float(x)
    except Exception:
        return float(default)

def inches_to_mm(x) -> float:
    return fnum(x) * 25.4

def safe_calculate_total_width_mm(writer: ImageWriter, code_obj, module_width_mm, quiet_mm) -> float:
    """Support both signatures of calculate_size; always return float width incl. quiet zone."""
    fullcode = code_obj.get_fullcode()
    mw = fnum(module_width_mm)
    qz = fnum(quiet_mm)
    try:
        # newer signature: (fullcode, module_width, quiet_zone)
        w_mm, _ = writer.calculate_size(fullcode, mw, qz)
        return fnum(w_mm)
    except TypeError:
        # older signature: (fullcode, module_width) -> add quiet zone manually
        w_mm, _ = writer.calculate_size(fullcode, mw)
        return fnum(w_mm) + qz * 2.0

def render_png(data: str, dpi, module_width_mm, module_height_mm, quiet_mm) -> BytesIO:
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
    code.write(buf, opts)
    buf.seek(0)
    return buf

def fit_width_mm(data: str, target_width_mm, dpi, height_mm, quiet_mm,
                 mw_low=0.02, mw_high=0.8, tol=0.02):
    """Binary-search module_width so final width == target."""
    data = sanitize_ascii(data)
    if not data:
        raise ValueError("النص بعد التنقية فارغ.")

    writer = ImageWriter()
    code = Code128(data, writer=writer)

    low, high = fnum(mw_low), fnum(mw_high)
    target = fnum(target_width_mm)
    qz = fnum(quiet_mm)
    best_mw, best_err = None, 1e9

    # tighten search
    while (high - low) > 1e-5:
        mid = (low + high) / 2.0
        total_w_mm = safe_calculate_total_width_mm(writer, code, mid, qz)
        err = total_w_mm - target

        if abs(err) < best_err:
            best_err, best_mw = abs(err), mid

        if err > 0:
            high = mid    # too wide -> shrink
        else:
            low = mid     # too narrow -> enlarge

        if abs(err) <= fnum(tol):
            best_mw = mid
            break

    png_buf = render_png(data, dpi, best_mw, fnum(height_mm), qz)
    return png_buf, best_mw, data

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

            png_buf, mw_used, used_data = fit_width_mm(
                clean, target_w_mm, dpi, height_mm, quiet_mm
            )

            # expected pixel dims (for sanity check at printer dialog)
            px_w = int(round((target_w_mm / 25.4) * fnum(dpi)))
            px_h = int(round((height_mm   / 25.4) * fnum(dpi)))

            st.image(png_buf, caption=f"عرض مضبوط ≈ {fnum(width_in):.2f}″ | ارتفاع ≈ {fnum(height_in):.2f}″ | mw≈{fnum(mw_used):.3f} مم", use_container_width=True)
            st.download_button("⬇️ تحميل PNG", data=png_buf, file_name="code128.png", mime="image/png")
            st.success(f"جاهز للطباعة 100% بدون Fit to page. الأبعاد المتوقعة عند {dpi} DPI ≈ {px_w}×{px_h} بكسل.")
        except Exception as e:
            st.error(f"تعذّر الإنشاء: {e}")
