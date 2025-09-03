# -*- coding: utf-8 -*-
import re, base64
from io import BytesIO
from datetime import datetime, date, time, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

import streamlit as st
import qrcode
from PIL import Image
import cv2  # للتحقق من QR عبر الصورة

from barcode import Code128
from barcode.writer import ImageWriter

# ---------------- إعداد عام ----------------
st.set_page_config(page_title="حاسبة + ZATCA QR + تحقق + Code128", page_icon="💰", layout="centered")
st.title("💰 حاسبة الضريبة + مولّد QR (ZATCA) + تحقّق تلقائي + باركود Code-128")

# حالة مشتركة لإرسال قيم الحاسبة
st.session_state.setdefault("push_total", None)
st.session_state.setdefault("push_vat", None)

# ============================ قسم 1: حاسبة الضريبة ============================
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
        st.success("تم الإرسال ✅")

# ============================ أدوات ZATCA المعيارية ============================
def _clean_vat(v: str) -> str:
    return re.sub(r"\D", "", v or "")

def _fmt2(x: str) -> str:
    """تثبيت رقمين عشريين بنقطة وبـ ROUND_HALF_UP"""
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
        raise ValueError("قيمة TLV أطول من 255 بايت (غير مسموح في مرحلة 1).")
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

def parse_tlv(payload: bytes) -> dict:
    """تفكيك TLV → dict مع الحقول 1..5"""
    out = {}
    i = 0
    while i + 2 <= len(payload):
        tag = payload[i]; ln = payload[i+1]; i += 2
        if i + ln > len(payload):  # حماية
            break
        val = payload[i:i+ln]; i += ln
        out[tag] = val.decode("utf-8", errors="replace")
    return out

def validate_zatca_fields(fields: dict) -> dict:
    """فحوصات سريعة وفق المواصفة"""
    verdict = {}

    # 1- اسم البائع
    verdict["seller_name"] = {"value": fields.get(1, ""), "ok": bool(fields.get(1))}

    # 2- الرقم الضريبي
    vat = _clean_vat(fields.get(2, ""))
    verdict["vat"] = {"value": vat, "ok": len(vat) == 15}

    # 3- التاريخ ISO8601Z
    ts = fields.get(3, "")
    iso_ok = bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", ts))
    verdict["timestamp"] = {"value": ts, "ok": iso_ok}

    # 4- الإجمالي
    try:
        tot = Decimal(fields.get(4, "0"))
        verdict["total"] = {"value": f"{tot:.2f}", "ok": True}
    except InvalidOperation:
        verdict["total"] = {"value": fields.get(4, ""), "ok": False}

    # 5- الضريبة
    try:
        vat_amt = Decimal(fields.get(5, "0"))
        verdict["vat_amount"] = {"value": f"{vat_amt:.2f}", "ok": True}
    except InvalidOperation:
        verdict["vat_amount"] = {"value": fields.get(5, ""), "ok": False}

    return verdict

# ============================ قسم 2: مولّد ZATCA QR ============================
st.header("🔖 مولّد رمز QR (ZATCA) – TLV → Base64")

vat_number = st.text_input("الرقم الضريبي (15 رقم)", max_chars=15)
seller_name = st.text_input("اسم البائع")
total = st.text_input("الإجمالي (شامل)", value=str(st.session_state.get("push_total") or "0.00"))
vat_only = st.text_input("الضريبة", value=str(st.session_state.get("push_vat") or "0.00"))

today = date.today()
now_t = datetime.now().time().replace(second=0, microsecond=0)
d_val = st.date_input("التاريخ", value=today)
t_val = st.time_input("الوقت", value=now_t, step=60)  # دقيقة واحدة

if st.button("إنشاء رمز QR (ZATCA)"):
    vat = _clean_vat(vat_number)
    if len(vat) != 15:
        st.error("الرقم الضريبي يجب أن يكون 15 رقمًا بالضبط.")
    elif not seller_name.strip():
        st.error("أدخل اسم البائع.")
    else:
        iso = _iso_utc(d_val, t_val)
        total_str = _fmt2(total)
        vat_str   = _fmt2(vat_only)

        try:
            b64 = build_zatca_base64(seller_name.strip(), vat, iso, total_str, vat_str)
        except ValueError as e:
            st.error(f"خطأ في TLV: {e}")
        else:
            st.subheader("Base64 الناتج")
            st.code(b64, language="text")

            # توليد صورة QR من نفس الـ Base64
            qr = qrcode.QRCode(box_size=8, border=2)
            qr.add_data(b64); qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO(); img.save(buf, format="PNG")
            st.image(buf.getvalue(), caption="رمز QR ZATCA")
            st.download_button("⬇️ تحميل QR", buf.getvalue(), file_name="zatca_qr.png", mime="image/png")

# ============================ قسم 3: تحقّق تلقائي من قارئ ============================
st.header("🛡️ تحقّق تلقائي من رمز ZATCA")

tab1, tab2 = st.tabs(["📷 رفع صورة QR", "📋 لصق Base64"])
with tab1:
    up = st.file_uploader("ارفع صورة للـ QR (PNG/JPG)", type=["png", "jpg", "jpeg"])
    if up is not None:
        # نقرأ الصورة بـ OpenCV ونفكّ QR
        image_bytes = up.read()
        npbuf = np.frombuffer(image_bytes, dtype="uint8")  # numpy سيأتي من cv2
        img = cv2.imdecode(npbuf, cv2.IMREAD_GRAYSCALE)
        detector = cv2.QRCodeDetector()
        data, pts, _ = detector.detectAndDecode(img)
        if not data:
            st.error("تعذّر قراءة QR من الصورة.")
        else:
            st.success("تمت قراءة محتوى QR.")
            pasted_b64 = data.strip()
            st.code(pasted_b64, language="text")

            # نحاول فك Base64 → TLV
            try:
                payload = base64.b64decode(pasted_b64, validate=True)
                fields = parse_tlv(payload)
                verdict = validate_zatca_fields(fields)
                st.subheader("الحقول المفكّكة")
                st.json({k: v["value"] for k, v in verdict.items()})
                # ملخص صلاحية
                ok_all = all(v["ok"] for v in verdict.values())
                st.success("✅ صالح وفق المواصفة." if ok_all else "⚠️ بعض الحقول غير صحيحة.")
            except Exception as e:
                st.error(f"Base64 غير صالح أو TLV غير صحيح: {e}")

with tab2:
    pasted_b64 = st.text_area("الصق Base64 هنا")
    if st.button("تحقّق"):
        try:
            payload = base64.b64decode((pasted_b64 or "").strip(), validate=True)
            fields = parse_tlv(payload)
            verdict = validate_zatca_fields(fields)
            st.subheader("الحقول المفكّكة")
            st.json({k: v["value"] for k, v in verdict.items()})
            ok_all = all(v["ok"] for v in verdict.values())
            st.success("✅ صالح وفق المواصفة." if ok_all else "⚠️ بعض الحقول غير صحيحة.")
        except Exception as e:
            st.error(f"Base64 غير صالح أو TLV غير صحيح: {e}")

# ============================ قسم 4: باركود Code-128 (جرير) ============================
st.header("🧾 مولّد باركود Code-128 (بدون نص سفلي)")

# مقاس افتراضي (جرير)
WIDTH_IN, HEIGHT_IN, DPI, QUIET_MM = 1.86, 0.28, 600, 0.0

def inches_to_mm(x): return float(x) * 25.4
def px_from_in(inches, dpi): return int(round(float(inches) * int(dpi)))

# تنظيف نص code128
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
