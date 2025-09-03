# -*- coding: utf-8 -*-
import re, base64
from io import BytesIO
from datetime import datetime, date, time, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

import streamlit as st
import qrcode
from qrcode.constants import ERROR_CORRECT_M, ERROR_CORRECT_L
from PIL import Image
from barcode import Code128
from barcode.writer import ImageWriter

# ================= إعداد عام =================
st.set_page_config(page_title="حاسبة + ZATCA + كثافة عالية + Code128", page_icon="💰", layout="centered")
st.title("💰 حاسبة الضريبة + مولّد QR (ZATCA) كثيف 2025 + باركود Code-128")

# حالة مشتركة لحقول قسم QR (إرسال القيم من الحاسبة)
st.session_state.setdefault("qr_total", "0.00")
st.session_state.setdefault("qr_vat", "0.00")

# =============== أدوات ZATCA المعيارية ===============
def _clean_vat(v: str) -> str:
    return re.sub(r"\D", "", v or "")

def _fmt2(x: str) -> str:
    """ضبط رقمين عشريين مع تقريب تجاري HALF_UP وفاصل عشري نقطة"""
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
    if len(vb) > 255:
        raise ValueError("قيمة TLV أطول من 255 بايت (مرحلة 1).")
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

# =============== مولِّد QR كثيف بصريًا (ستايل 2025) ===============
def make_qr_dense(b64_text: str,
                  *, version: int = 14,       # نسخة أعلى = مربعات أكثر (كثافة أعلى)
                  error_correction=ERROR_CORRECT_M,  # توازن جيد؛ جرّب L لو تبغى مربعات أدق
                  border: int = 4,             # هامش قياسي
                  base_box: int = 2,           # حجم الوحدة قبل التكبير (صغير جدًا)
                  final_px: int = 640          # نكبّر حادًا لهذا المقاس
                 ) -> bytes:
    qr = qrcode.QRCode(
        version=version,
        error_correction=error_correction,
        box_size=base_box,
        border=border,
    )
    qr.add_data(b64_text)
    qr.make(fit=False)  # لا نسمح له بالنزول لنسخة أقل

    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((final_px, final_px), Image.NEAREST)  # تكبير حاد يحافظ على الحواف
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()

# ================= قسم 1: حاسبة الضريبة =================
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
        st.session_state["qr_total"] = f"{total_incl:.2f}"
        st.session_state["qr_vat"]   = f"{ta:.2f}"
        st.toast("تم إرسال الإجمالي والضريبة إلى قسم QR ✅")
        st.rerun()

# ================= قسم 2: مولّد ZATCA QR =================
st.header("🔖 مولّد رمز QR (ZATCA) – TLV → Base64 (نمط كثيف 2025)")

vat_number  = st.text_input("الرقم الضريبي (15 رقم)", max_chars=15)
seller_name = st.text_input("اسم البائع")

# الحقول مرتبطة مباشرة بالحالة لضمان استقبال الإرسال
total_str = st.text_input("الإجمالي (شامل)", key="qr_total")
vat_str   = st.text_input("الضريبة", key="qr_vat")

today = date.today()
now_t = datetime.now().time().replace(second=0, microsecond=0)
d_val = st.date_input("التاريخ", value=today)
t_val = st.time_input("الوقت", value=now_t, step=60)

# اختيار نمط المظهر (كثيف/قياسي)
dense_mode = st.toggle("نمط كثيف (مظهر 2025)", value=True)

if st.button("إنشاء رمز QR (ZATCA)"):
    vat = _clean_vat(vat_number)
    if len(vat) != 15:
        st.error("الرقم الضريبي يجب أن يكون 15 رقمًا بالضبط.")
    elif not seller_name.strip():
        st.error("أدخل اسم البائع.")
    else:
        iso = _iso_utc(d_val, t_val)
        total_fmt = _fmt2(total_str)
        vat_fmt   = _fmt2(vat_str)

        try:
            b64 = build_zatca_base64(seller_name.strip(), vat, iso, total_fmt, vat_fmt)
        except ValueError as e:
            st.error(f"خطأ في TLV: {e}")
        else:
            st.subheader("Base64 الناتج")
            st.code(b64, language="text")

            if dense_mode:
                # إعدادات كثيفة (قريبة من فواتير 2025)
                png_bytes = make_qr_dense(
                    b64,
                    version=14,                # كثافة أعلى
                    error_correction=ERROR_CORRECT_M,
                    border=4,
                    base_box=2,                # وحدات صغيرة
                    final_px=640               # صورة نهائية حادة كبيرة
                )
            else:
                # شكل قياسي قديم (fit=True)
                qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=8, border=4)
                qr.add_data(b64); qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
                buf = BytesIO(); img.save(buf, format="PNG")
                png_bytes = buf.getvalue()

            st.image(png_bytes, caption="رمز QR ZATCA")
            st.download_button("⬇️ تحميل QR", png_bytes, file_name="zatca_qr.png", mime="image/png")
            st.success("تم الإنشاء وفق ZATCA TLV Base64.")

# ================= قسم 3: باركود Code-128 (بدون نص سفلي) =================
st.header("🧾 مولّد باركود Code-128 (بدون نص سفلي)")

# مقاس افتراضي (جرير)
WIDTH_IN, HEIGHT_IN, DPI, QUIET_MM = 1.86, 0.28, 600, 0.0

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
        "quiet_zone": float(QUIET_MM),
        "background": "white",
        "foreground": "black",
    }
    code = Code128(data, writer=writer)
    buf = BytesIO(); code.write(buf, opts)
    return buf.getvalue()

def resize_to_exact(png_bytes: bytes, target_w_px: int, target_h_px: int) -> bytes:
    with Image.open(BytesIO(png_bytes)) as im:
        resized = im.resize((target_w_px, target_h_px), Image.NEAREST)
        out = BytesIO(); resized.save(out, format="PNG", dpi=(DPI, DPI))
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
            st.success("الطباعة: Scale = 100%، بدون Fit to page.")
        except Exception as e:
            st.error(f"تعذّر الإنشاء: {e}")
