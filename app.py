# -*- coding: utf-8 -*-
import re, json, base64
from io import BytesIO
from datetime import datetime, date, time, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

import streamlit as st
import qrcode
from qrcode.constants import ERROR_CORRECT_M
from PIL import Image
from barcode import Code128
from barcode.writer import ImageWriter

# ================= إعداد عام =================
st.set_page_config(page_title="حاسبة الضريبة + QR + Code128", page_icon="💰", layout="wide")

# ================= CSS للتنسيق =================
st.markdown("""
    <style>
    body {
        background-color: #b8860b;
    }
    .main > div {
        background-color: #fdf6e3;
        padding: 20px;
        border-radius: 12px;
    }
    h1, h2, h3 {
        text-align: center;
        color: black;
    }
    .stButton > button {
        background-color: #228B22;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        padding: 8px 16px;
    }
    .stButton > button:hover {
        background-color: #006400;
    }
    .stTextInput > div > div > input {
        border-radius: 6px;
        padding: 6px;
    }
    </style>
""", unsafe_allow_html=True)

# ================= العنوان =================
st.markdown("<h1>حاسبة الضريبة + مولد QR (ZATCA) + Code128</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;'>برمجة يوسف الأنسي</p>", unsafe_allow_html=True)

# ================= دوال مساعدة =================
def _clean_vat(v: str) -> str:
    return re.sub(r"\D", "", v or "")

def _fmt2(x: str) -> str:
    try:
        q = Decimal(x)
    except InvalidOperation:
        q = Decimal("0")
    q = q.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return format(q, "f")

def _iso_utc(dt_date: date, dt_time: time) -> str:
    local_dt = datetime.combine(dt_date, dt_time.replace(second=0, microsecond=0))
    return local_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _tlv(tag: int, value: str) -> bytes:
    vb = value.encode("utf-8")
    return bytes([tag, len(vb)]) + vb

def build_zatca_base64(seller: str, vat: str, dt_iso: str, total_s: str, vat_s: str) -> str:
    payload = b"".join([
        _tlv(1, seller),
        _tlv(2, vat),
        _tlv(3, dt_iso),
        _tlv(4, total_s),
        _tlv(5, vat_s),
    ])
    return base64.b64encode(payload).decode("ascii")

def make_qr_dense(b64_text: str, *, version: int = 14,
                  error_correction=ERROR_CORRECT_M, border: int = 4,
                  base_box: int = 2, final_px: int = 400) -> bytes:
    qr = qrcode.QRCode(
        version=version,
        error_correction=error_correction,
        box_size=base_box,
        border=border,
    )
    qr.add_data(b64_text)
    qr.make(fit=False)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((final_px, final_px), Image.NEAREST)
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()

# ============ إعداد Code128 ============
WIDTH_IN, HEIGHT_IN, DPI = 1.86, 0.31, 600

def inches_to_mm(x): return float(x) * 25.4
def px_from_in(inches, dpi): return int(round(float(inches) * int(dpi)))

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
def sanitize(s: str) -> str:
    s = (s or "").translate(ARABIC_DIGITS)
    s = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]", "", s)
    return "".join(ch for ch in s if ord(ch) < 128).strip()

def render_barcode_png_bytes(data: str) -> bytes:
    writer = ImageWriter()
    opts = {
        "write_text": False,
        "dpi": int(DPI),
        "module_height": 15.0,
        "quiet_zone": 0.0,
        "text_distance": 0.0,
        "background": "white",
        "foreground": "black",
    }
    code = Code128(data, writer=writer)
    buf = BytesIO()
    code.write(buf, opts)
    buf.seek(0)

    img = Image.open(buf).convert("RGB")
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)

    target_w_px = px_from_in(WIDTH_IN, DPI)
    target_h_px = px_from_in(HEIGHT_IN, DPI)
    img = img.resize((target_w_px, target_h_px), Image.NEAREST)

    out = BytesIO()
    img.save(out, format="PNG", dpi=(DPI, DPI))
    return out.getvalue()

# ================= القسم 1: حاسبة الضريبة =================
st.header("📊 حاسبة الضريبة")
total_incl = st.number_input("المبلغ شامل الضريبة", min_value=0.0, step=0.01)
tax_rate = st.number_input("نسبة الضريبة (%)", min_value=1.0, max_value=100.0, value=15.0, step=0.01)

if st.button("احسب الآن"):
    rate = tax_rate / 100.0
    before_tax = round(total_incl / (1 + rate), 2)
    tax_amount = round(total_incl - before_tax, 2)
    st.success(f"السعر قبل الضريبة: {before_tax:.2f} | مبلغ الضريبة: {tax_amount:.2f}")

    st.session_state["qr_total"] = f"{total_incl:.2f}"
    st.session_state["qr_vat"]   = f"{tax_amount:.2f}"

# ================= القسم 2: مولد QR =================
st.header("🔖 مولد رمز QR (ZATCA)")
vat_number = st.text_input("الرقم الضريبي (15 رقم)")
seller_name = st.text_input("اسم البائع", key="seller_name")

total_str = st.text_input("الإجمالي (شامل)", value=st.session_state.get("qr_total", "0.00"))
vat_str   = st.text_input("الضريبة", value=st.session_state.get("qr_vat", "0.00"))

d_val = st.date_input("التاريخ", value=date.today())
t_val = st.time_input("الوقت", value=datetime.now().time().replace(second=0, microsecond=0))

if st.button("إنشاء رمز QR"):
    iso = _iso_utc(d_val, t_val)
    b64 = build_zatca_base64(seller_name.strip(), _clean_vat(vat_number), iso, _fmt2(total_str), _fmt2(vat_str))
    qr_png = make_qr_dense(b64)
    st.image(qr_png, caption="رمز QR ZATCA")
    st.download_button("⬇️ تحميل رمز QR", qr_png, file_name="zatca_qr.png", mime="image/png")

# ================= القسم 3: مولد Code128 =================
st.header("🧾 مولد باركود Code-128 (1.86 × 0.31 inch @ 600 DPI)")
code128_val = st.text_input("أدخل الرقم/النص (Code-128)")
if st.button("إنشاء Code-128"):
    clean = sanitize(code128_val)
    if not clean:
        st.error("أدخل نصًا صالحًا.")
    else:
        try:
            final_png = render_barcode_png_bytes(clean)
            st.image(final_png, caption=f"{WIDTH_IN} × {HEIGHT_IN} inch @ {DPI} DPI")
            st.download_button("⬇️ تحميل Code-128", final_png, file_name="code128.png", mime="image/png")
            st.success("✅ تم إنشاء الباركود بالمقاسات الدقيقة.")
        except Exception as e:
            st.error(f"تعذر الإنشاء: {e}")
