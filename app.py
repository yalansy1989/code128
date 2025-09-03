# -*- coding: utf-8 -*-
import re, base64
from io import BytesIO
from datetime import datetime, timezone
import streamlit as st
import qrcode
from PIL import Image
from barcode import Code128
from barcode.writer import ImageWriter

# إعداد الصفحة
st.set_page_config(page_title="حاسبة + QR + Code128", page_icon="💰", layout="centered")
st.title("💰 حاسبة الضريبة + مولّد QR (ZATCA) + باركود Code-128")

# ===== قسم 1: حاسبة الضريبة =====
st.header("📊 حاسبة الضريبة")

total_incl = st.number_input("المبلغ شامل الضريبة", min_value=0.0, step=0.01)
tax_rate = st.number_input("نسبة الضريبة (%)", min_value=1.0, max_value=100.0, value=15.0, step=0.01)

before_tax, tax_amount = 0.0, 0.0
if st.button("احسب الآن"):
    rate = tax_rate / 100.0
    before_tax = round(total_incl / (1 + rate), 2)
    tax_amount = round(total_incl - before_tax, 2)
    st.success(f"قبل الضريبة: {before_tax:.2f} | مبلغ الضريبة: {tax_amount:.2f}")

# ===== قسم 2: QR ZATCA =====
st.header("🔖 مولّد رمز QR (ZATCA)")

vat_number = st.text_input("الرقم الضريبي (15 رقم)", max_chars=15)
seller_name = st.text_input("اسم البائع")
total = st.number_input("الإجمالي (شامل)", min_value=0.0, step=0.01, value=total_incl or 0.0)
vat_only = st.number_input("الضريبة", min_value=0.0, step=0.01, value=tax_amount or 0.0)
invoice_date = st.datetime_input("التاريخ والوقت", value=datetime.now())

def tlv(tag, value: str) -> bytes:
    value_bytes = value.encode("utf-8")
    return bytes([tag, len(value_bytes)]) + value_bytes

def to_zatca_base64(seller, vat, dt, total, vat_amt):
    parts = [
        tlv(1, seller),
        tlv(2, vat),
        tlv(3, dt),
        tlv(4, f"{total:.2f}"),
        tlv(5, f"{vat_amt:.2f}"),
    ]
    return base64.b64encode(b"".join(parts)).decode("utf-8")

if st.button("إنشاء رمز QR"):
    clean_vat = re.sub(r"\D", "", vat_number)
    if len(clean_vat) != 15:
        st.error("الرقم الضريبي يجب أن يكون 15 رقمًا بالضبط")
    elif not seller_name:
        st.error("أدخل اسم البائع")
    elif total <= 0 or vat_only <= 0:
        st.error("أدخل الإجمالي والضريبة")
    else:
        iso = invoice_date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        b64 = to_zatca_base64(seller_name, clean_vat, iso, total, vat_only)

        qr = qrcode.QRCode(box_size=8, border=2)
        qr.add_data(b64)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buf = BytesIO()
        img.save(buf, format="PNG")
        st.image(buf.getvalue(), caption="رمز QR ZATCA")
        st.download_button("⬇️ تحميل QR", buf.getvalue(), file_name="zatca_qr.png", mime="image/png")
        st.code(b64, language="text")

# ===== قسم 3: باركود Code-128 (جرير) =====
st.header("🔖 مولّد باركود Code-128 (مقاس جرير)")

# مقاسات جرير
WIDTH_IN  = 1.86
HEIGHT_IN = 0.28
DPI       = 600
QUIET_MM  = 0.0

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
        "module_height": inches_to_mm(HEIGHT_IN),
        "quiet_zone": QUIET_MM,
        "background": "white",
        "foreground": "black",
    }
    code = Code128(data, writer=writer)
    buf = BytesIO()
    code.write(buf, opts)
    return buf.getvalue()

def resize_to_exact(png_bytes: bytes, target_w_px: int, target_h_px: int) -> bytes:
    with Image.open(BytesIO(png_bytes)) as im:
        resized = im.resize((target_w_px, target_h_px), Image.NEAREST)
        out = BytesIO()
        resized.save(out, format="PNG", dpi=(DPI, DPI))
        return out.getvalue()

num = st.text_input("أدخل الرقم/النص (للكود 128)")
if st.button("إنشاء الكود 128"):
    clean = sanitize(num)
    if not clean:
        st.error("أدخل رقمًا/نصًا صالحًا.")
    else:
        try:
            raw_png = render_barcode_png_bytes(clean)
            w_px = px_from_in(WIDTH_IN, DPI)
            h_px = px_from_in(HEIGHT_IN, DPI)
            final_png = resize_to_exact(raw_png, w_px, h_px)

            st.image(final_png, caption=f"{WIDTH_IN}×{HEIGHT_IN} inch @ {DPI} DPI")
            st.download_button("⬇️ تحميل Code128", final_png, file_name="code128.png", mime="image/png")
            st.success("الكود يملأ الصورة بالكامل. اطبع بنسبة 100% بدون Fit to page.")
        except Exception as e:
            st.error(f"تعذّر الإنشاء: {e}")
