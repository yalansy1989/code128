# -*- coding: utf-8 -*-
import re, base64
from io import BytesIO
from datetime import datetime, timezone
import streamlit as st
import qrcode
from PIL import Image
from barcode import Code128
from barcode.writer import ImageWriter

# ---------------- إعداد عام ----------------
st.set_page_config(page_title="حاسبة + QR + Code128", page_icon="💰", layout="centered")
st.title("💰 حاسبة الضريبة + مولّد QR (ZATCA) + باركود Code-128")

# مفاتيح حالة مشتركة
for k, v in {
    "push_total": None,
    "push_vat": None,
}.items():
    st.session_state.setdefault(k, v)

# ---------------- قسم 1: حاسبة الضريبة ----------------
st.header("📊 حاسبة الضريبة")

colA, colB = st.columns(2)
with colA:
    total_incl = st.number_input("المبلغ شامل الضريبة", min_value=0.0, step=0.01)
with colB:
    tax_rate = st.number_input("نسبة الضريبة (%)", min_value=1.0, max_value=100.0, value=15.0, step=0.01)

before_tax = tax_amount = 0.0
c1, c2 = st.columns(2)
with c1:
    if st.button("احسب الآن"):
        rate = tax_rate / 100.0
        before_tax = round(total_incl / (1 + rate), 2)
        tax_amount = round(total_incl - before_tax, 2)
        st.success(f"قبل الضريبة: {before_tax:.2f} | مبلغ الضريبة: {tax_amount:.2f}")
with c2:
    if st.button("📤 إرسال القيم إلى قسم QR"):
        rate = tax_rate / 100.0 if tax_rate else 0.0
        bt = round(total_incl / (1 + rate), 2) if total_incl and rate else 0.0
        ta = round(total_incl - bt, 2) if total_incl and rate else 0.0
        st.session_state.push_total = round(total_incl or 0.0, 2)
        st.session_state.push_vat = round(ta or 0.0, 2)
        st.success("تم إرسال الإجمالي والضريبة إلى قسم QR ✅")

# ---------------- قسم 2: مولّد QR ZATCA ----------------
st.header("🔖 مولّد رمز QR (ZATCA)")

# قيم افتراضية من الحاسبة إن وُجدت
def _pref(key, fallback):
    return st.session_state[key] if st.session_state.get(key) is not None else fallback

vat_number = st.text_input("الرقم الضريبي (15 رقم)", max_chars=15)
seller_name = st.text_input("اسم البائع")
total = st.number_input("الإجمالي (شامل)", min_value=0.0, step=0.01, value=_pref("push_total", 0.0))
vat_only = st.number_input("الضريبة", min_value=0.0, step=0.01, value=_pref("push_vat", 0.0))
invoice_date = st.datetime_input("التاريخ والوقت", value=datetime.now())

def tlv(tag, value: str) -> bytes:
    vb = value.encode("utf-8")
    return bytes([tag, len(vb)]) + vb

def to_zatca_base64(seller, vat, dt_iso, total_val, vat_val):
    parts = [
        tlv(1, seller),
        tlv(2, vat),
        tlv(3, dt_iso),
        tlv(4, f"{total_val:.2f}"),
        tlv(5, f"{vat_val:.2f}"),
    ]
    return base64.b64encode(b"".join(parts)).decode("utf-8")

if st.button("إنشاء رمز QR"):
    clean_vat = re.sub(r"\D", "", vat_number or "")
    if len(clean_vat) != 15:
        st.error("الرقم الضريبي يجب أن يكون 15 رقمًا بالضبط.")
    elif not seller_name:
        st.error("أدخل اسم البائع.")
    elif total <= 0 or vat_only < 0:
        st.error("أدخل الإجمالي والضريبة (الضريبة يمكن أن تكون 0.00).")
    else:
        iso = invoice_date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        b64 = to_zatca_base64(seller_name, clean_vat, iso, total, vat_only)
        qr = qrcode.QRCode(box_size=8, border=2)
        qr.add_data(b64); qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO(); img.save(buf, format="PNG")
        st.image(buf.getvalue(), caption="رمز QR ZATCA")
        st.download_button("⬇️ تحميل QR", buf.getvalue(), file_name="zatca_qr.png", mime="image/png")
        st.code(b64, language="text")

# ---------------- قسم 3: باركود Code-128 (مضبوط) ----------------
st.header("🧾 مولّد باركود Code-128 (بدون نص سفلي)")

# مقاس افتراضي (يمكنك تعديله هنا لو احتجت)
WIDTH_IN  = 1.86
HEIGHT_IN = 0.28
DPI       = 600
QUIET_MM  = 0.0  # بدون هوامش خارجية

def inches_to_mm(x): return float(x) * 25.4
def px_from_in(inches, dpi): return int(round(float(inches) * int(dpi)))

# تنظيف النص لمنع مشاكل RTL/محارف خفية
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
def sanitize(s: str) -> str:
    s = (s or "").translate(ARABIC_DIGITS)
    s = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]", "", s)
    return "".join(ch for ch in s if ord(ch) < 128).strip()

def render_barcode_png_bytes(data: str) -> bytes:
    writer = ImageWriter()
    opts = {
        "write_text": False,                         # بدون الرقم أسفل الباركود
        "dpi": int(DPI),
        "module_height": inches_to_mm(HEIGHT_IN),    # ارتفاع الأشرطة بالملّيمتر
        "quiet_zone": float(QUIET_MM),               # بدون هامش خارجي
        "background": "white",
        "foreground": "black",
    }
    code = Code128(data, writer=writer)
    buf = BytesIO()
    code.write(buf, opts)
    return buf.getvalue()

def resize_to_exact(png_bytes: bytes, target_w_px: int, target_h_px: int) -> bytes:
    # يملأ الصورة بالكامل بدون Padding (قد يغيّر سماكات البارات خطيًا—NEAREST يحافظ على الحدة)
    with Image.open(BytesIO(png_bytes)) as im:
        resized = im.resize((target_w_px, target_h_px), Image.NEAREST)
        out = BytesIO()
        resized.save(out, format="PNG", dpi=(DPI, DPI))
        return out.getvalue()

code128_val = st.text_input("أدخل الرقم/النص (Code-128)")
if st.button("إنشاء الكود 128"):
    clean = sanitize(code128_val)
    if not clean:
        st.error("أدخل رقمًا/نصًا صالحًا.")
    else:
        try:
            raw_png = render_barcode_png_bytes(clean)
            target_w_px = px_from_in(WIDTH_IN, DPI)
            target_h_px = px_from_in(HEIGHT_IN, DPI)
            final_png = resize_to_exact(raw_png, target_w_px, target_h_px)
            st.image(final_png, caption=f"{WIDTH_IN}×{HEIGHT_IN} inch @ {DPI} DPI")
            st.download_button("⬇️ تحميل Code-128", final_png, file_name="code128.png", mime="image/png")
            st.success("الكود يملأ الصورة بالكامل. في الطباعة: Scale = 100%، ألغِ Fit to page.")
        except Exception as e:
            st.error(f"تعذّر الإنشاء: {e}")
