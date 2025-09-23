# -*- coding: utf-8 -*-
import re, json, base64, io
from io import BytesIO
from datetime import datetime, date, time, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

import streamlit as st
import qrcode
from qrcode.constants import ERROR_CORRECT_M
from PIL import Image
from barcode import Code128
from barcode.writer import ImageWriter
from pypdf import PdfReader, PdfWriter   # ✅ مكتبة مدعومة

# ================= إعداد عام =================
st.set_page_config(page_title="💰 حاسبة + ZATCA 2025 + Code128 + Metadata", page_icon="💰", layout="wide")
st.title("💰 حاسبة الضريبة + مولّد  (ZATCA) + QR باركود Code-128 + أداة Edit Metadata")

# حالة مشتركة
st.session_state.setdefault("qr_total", "0.00")
st.session_state.setdefault("qr_vat", "0.00")
st.session_state.setdefault("seller_name", "")
st.session_state.setdefault("vat_book", {})

# =============== أدوات ZATCA ===============
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

# =============== مولّد QR ===============
def make_qr_dense(b64_text: str, version: int = 14, border: int = 4, base_box: int = 2, final_px: int = 640) -> bytes:
    qr = qrcode.QRCode(version=version, error_correction=ERROR_CORRECT_M, box_size=base_box, border=border)
    qr.add_data(b64_text)
    qr.make(fit=False)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((final_px, final_px), Image.NEAREST)
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()

# =============== باركود Code128 ===============
WIDTH_IN, HEIGHT_IN, DPI, QUIET_MM = 1.86, 0.31, 600, 0.0

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

# =============== PDF Metadata ===============
def pdf_date_to_display_date(pdf_date_str):
    if not pdf_date_str or not isinstance(pdf_date_str, str): return ""
    if pdf_date_str.startswith("D:"): pdf_date_str = pdf_date_str[2:]
    match = re.match(r"^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", pdf_date_str)
    if match:
        year, month, day, hour, minute, second = match.groups()
        try:
            dt_object = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
            return dt_object.strftime("%d/%m/%Y, %H:%M:%S")
        except ValueError:
            return pdf_date_str
    return pdf_date_str

def display_date_to_pdf_date(display_date_str):
    if not display_date_str or not isinstance(display_date_str, str): return ""
    try:
        dt_object = datetime.strptime(display_date_str, "%d/%m/%Y, %H:%M:%S")
        return dt_object.strftime("D:%Y%m%d%H%M%S+03'00'")
    except ValueError:
        return display_date_str

def read_pdf_metadata(pdf_file):
    pdf_file.seek(0)
    reader = PdfReader(pdf_file)
    metadata = reader.metadata
    processed_metadata = {}
    if metadata:
        for key, value in metadata.items():
            if key in ['/ModDate', '/CreationDate']:
                processed_metadata[key] = pdf_date_to_display_date(value)
            else:
                processed_metadata[key] = value
    return processed_metadata

def update_pdf_metadata(pdf_file, new_metadata):
    pdf_file.seek(0)
    reader = PdfReader(pdf_file)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    final_metadata = {}
    for key, value in new_metadata.items():
        if key in ['/ModDate', '/CreationDate']:
            final_metadata[key] = display_date_to_pdf_date(value)
        else:
            final_metadata[key] = value
    writer.add_metadata(final_metadata)
    output_pdf_bytes = io.BytesIO()
    writer.write(output_pdf_bytes)
    output_pdf_bytes.seek(0)
    return output_pdf_bytes

# --- Callback لمزامنة التاريخ ---
def update_creation_date_callback():
    if st.session_state.get("sync_dates", True):
        if "moddate_input" in st.session_state:
            st.session_state.creationdate_input = st.session_state.moddate_input

# =============== واجهة المستخدم ===============
# الصف الأول: حاسبة الضريبة + مولد QR
col1, col2 = st.columns(2)
with col1:
    st.markdown("### 📊 حاسبة الضريبة")
    total_incl = st.number_input("المبلغ شامل الضريبة", min_value=0.0, step=0.01)
    tax_rate = st.number_input("نسبة الضريبة (%)", min_value=1.0, max_value=100.0, value=15.0, step=0.01)
    if st.button("احسب الآن"):
        rate = tax_rate / 100.0
        before_tax = round(total_incl / (1 + rate), 2)
        tax_amount = round(total_incl - before_tax, 2)
        st.success(f"قبل الضريبة: {before_tax:.2f} | مبلغ الضريبة: {tax_amount:.2f}")

with col2:
    st.markdown("### 🔖 مولّد رمز QR (ZATCA)")
    vat_number = st.text_input("الرقم الضريبي (15 رقم)", max_chars=15)
    seller_name = st.text_input("اسم البائع", key="seller_name")
    total_str = st.text_input("الإجمالي (شامل)", key="qr_total")
    vat_str   = st.text_input("الضريبة", key="qr_vat")
    today = date.today()
    now_t = datetime.now().time().replace(second=0, microsecond=0)
    d_val = st.date_input("التاريخ", value=today)
    t_val = st.time_input("الوقت", value=now_t, step=60)
    if st.button("إنشاء رمز QR"):
        iso = _iso_utc(d_val, t_val)
        b64 = build_zatca_base64(seller_name.strip(), vat_number, iso, total_str, vat_str)
        png_bytes = make_qr_dense(b64)
        st.image(png_bytes, caption="رمز QR ZATCA")
        st.download_button("⬇️ تحميل QR", png_bytes, file_name="zatca_qr.png", mime="image/png")

# الصف الثاني: Code128 + Metadata
col3, col4 = st.columns(2)
with col3:
    st.markdown("### 🧾 مولّد باركود Code-128")
    code128_val = st.text_input("أدخل الرقم/النص (Code-128)")
    if st.button("إنشاء الكود 128"):
        clean = sanitize(code128_val)
        if clean:
            raw_png = render_barcode_png_bytes(clean)
            final_png = resize_to_exact(raw_png, px_from_in(WIDTH_IN, DPI), px_from_in(HEIGHT_IN, DPI))
            st.image(final_png, caption=f"{WIDTH_IN}×{HEIGHT_IN} inch @ {DPI} DPI")
            st.download_button("⬇️ تحميل Code-128", final_png, file_name="code128.png", mime="image/png")

with col4:
    st.markdown("### 📑 أداة تعديل بيانات PDF Metadata")
    uploaded_file = st.file_uploader("قم بتحميل ملف PDF", type=["pdf"])
    if uploaded_file:
        st.success("تم تحميل الملف بنجاح!")

        if "metadata" not in st.session_state:
            st.session_state.metadata = read_pdf_metadata(uploaded_file)

        if st.session_state.metadata:
            st.subheader("بيانات التعريف الحالية")

            # ✅ خيار تحديث تلقائي أو يدوي
            st.checkbox("تحديث CreationDate تلقائياً مع ModDate", key="sync_dates", value=True)

            updated_metadata = {}
            for key, value in st.session_state.metadata.items():
                display_key = key[1:] if key.startswith("/") else key

                if key == "/ModDate":
                    updated_metadata[key] = st.text_input(
                        display_key,
                        value=value,
                        key="moddate_input",
                        on_change=update_creation_date_callback
                    )
                elif key == "/CreationDate":
                    updated_metadata[key] = st.text_input(
                        display_key,
                        value=st.session_state.get("creationdate_input", value),
                        key="creationdate_input"
                    )
                else:
                    updated_metadata[key] = st.text_input(display_key, value=value, key=key)

            if st.button("تحديث بيانات التعريف وحفظ الملف"):
                updated_pdf = update_pdf_metadata(uploaded_file, updated_metadata)
                if updated_pdf:
                    st.success("تم تحديث بيانات التعريف بنجاح!")
                    st.download_button("تحميل الملف المعدل", data=updated_pdf, file_name=uploaded_file.name)
