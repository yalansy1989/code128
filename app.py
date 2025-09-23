# -*- coding: utf-8 -*-
import re, base64, io
from io import BytesIO
from datetime import datetime, date, time, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

import streamlit as st
import qrcode
from qrcode.constants import ERROR_CORRECT_M
from PIL import Image
from barcode import Code128
from barcode.writer import ImageWriter
from pypdf import PdfReader, PdfWriter

# ---------------- إعداد عام + تنسيق ----------------
st.set_page_config(page_title="حاسبة + ZATCA + Code128 + PDF Metadata", page_icon="💰", layout="wide")
st.markdown("""
<style>
/* عناوين ديناميكية: أخضر فاتح / أبيض داكن */
h1, h2, h3 { text-align:center; font-weight:700; }
@media (prefers-color-scheme: light) { h1, h2, h3 { color:#046307 !important; } }
@media (prefers-color-scheme: dark)  { h1, h2, h3 { color:#ffffff !important; } }
/* بطاقات بسيطة */
.block-container { padding-top: 1.2rem; }
</style>
""", unsafe_allow_html=True)

st.title("💰 حاسبة الضريبة + مولّد QR (ZATCA) + Code128 + PDF Metadata")

# ---------------- أدوات مساعدة عامة ----------------
def _clean_vat(v: str) -> str: return re.sub(r"\D", "", v or "")

def _fmt2(x: str) -> str:
    try: q = Decimal(x)
    except InvalidOperation: q = Decimal("0")
    q = q.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return format(q, "f")

def _iso_utc(dt_date: date, dt_time: time) -> str:
    local_dt = datetime.combine(dt_date, dt_time.replace(second=0, microsecond=0))
    return local_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _tlv(tag: int, value: str) -> bytes:
    vb = value.encode("utf-8")
    if len(vb) > 255: raise ValueError("قيمة TLV أطول من 255 بايت.")
    return bytes([tag, len(vb)]) + vb

def build_zatca_base64(seller: str, vat: str, dt_iso: str, total_s: str, vat_s: str) -> str:
    payload = b"".join([_tlv(1, seller), _tlv(2, vat), _tlv(3, dt_iso), _tlv(4, total_s), _tlv(5, vat_s)])
    return base64.b64encode(payload).decode("ascii")

# ---------------- QR كثيف ----------------
def make_qr_dense(b64_text: str, *, version: int = 14, error_correction=ERROR_CORRECT_M,
                  border: int = 4, base_box: int = 2, final_px: int = 640) -> bytes:
    qr = qrcode.QRCode(version=version, error_correction=error_correction, box_size=base_box, border=border)
    qr.add_data(b64_text); qr.make(fit=False)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((final_px, final_px), Image.NEAREST)
    out = BytesIO(); img.save(out, format="PNG")
    return out.getvalue()

# ---------------- Code128 بدون هوامش وبالمقاس المطلوب ----------------
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

# ---------------- PDF Metadata (قراءة/كتابة + تنسيقات التاريخ) ----------------
def pdf_date_to_display_date(pdf_date_str):
    if not pdf_date_str or not isinstance(pdf_date_str, str): return ""
    if pdf_date_str.startswith("D:"): pdf_date_str = pdf_date_str[2:]
    m = re.match(r"^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", pdf_date_str)
    if m:
        y, M, d, H, m_, s = m.groups()
        try: return datetime(int(y), int(M), int(d), int(H), int(m_), int(s)).strftime("%d/%m/%Y, %H:%M:%S")
        except ValueError: return pdf_date_str
    return pdf_date_str

def display_date_to_pdf_date(display_date_str):
    if not display_date_str or not isinstance(display_date_str, str): return ""
    try:
        dt = datetime.strptime(display_date_str, "%d/%m/%Y, %H:%M:%S")
        return dt.strftime("D:%Y%m%d%H%M%S+03'00'")
    except ValueError:
        return display_date_str

def read_pdf_metadata(pdf_file):
    pdf_file.seek(0); reader = PdfReader(pdf_file)
    md = reader.metadata or {}
    out = {}
    for k, v in md.items():
        out[k] = pdf_date_to_display_date(v) if k in ("/ModDate", "/CreationDate") else v
    return out

def update_pdf_metadata(pdf_file, new_md):
    pdf_file.seek(0)
    reader = PdfReader(pdf_file)
    writer = PdfWriter()
    for p in reader.pages: writer.add_page(p)
    final_md = {}
    for k, v in new_md.items():
        final_md[k] = display_date_to_pdf_date(v) if k in ("/ModDate", "/CreationDate") else v
    writer.add_metadata(final_md)
    out = io.BytesIO(); writer.write(out); out.seek(0)
    return out

# -----------------------------------------------------
# الصف الأول: (الحاسبة) + (مولد QR)
# -----------------------------------------------------
c1, c2 = st.columns(2)

with c1:
    st.header("📊 حاسبة الضريبة")
    total_incl = st.number_input("المبلغ شامل الضريبة", min_value=0.0, step=0.01)
    tax_rate = st.number_input("نسبة الضريبة (%)", min_value=1.0, max_value=100.0, value=15.0, step=0.01)
    if st.button("احسب الآن"):
        rate = tax_rate / 100.0
        before_tax = round(total_incl / (1 + rate), 2)
        tax_amount = round(total_incl - before_tax, 2)
        st.success(f"قبل الضريبة: {before_tax:.2f} | مبلغ الضريبة: {tax_amount:.2f}")

with c2:
    st.header("🔖 مولّد رمز QR (ZATCA)")
    vat_number = st.text_input("الرقم الضريبي (15 رقم)", max_chars=15)
    seller_name = st.text_input("اسم البائع")
    total_str = st.text_input("الإجمالي (شامل)")
    vat_str   = st.text_input("الضريبة")
    d_val = st.date_input("التاريخ", value=date.today())
    t_val = st.time_input("الوقت", value=datetime.now().time().replace(second=0, microsecond=0), step=60)
    if st.button("إنشاء رمز QR"):
        vclean = _clean_vat(vat_number)
        if len(vclean) != 15:
            st.error("الرقم الضريبي يجب أن يكون 15 رقمًا.")
        else:
            b64 = build_zatca_base64(seller_name.strip(), vclean, _iso_utc(d_val, t_val), _fmt2(total_str), _fmt2(vat_str))
            st.code(b64, language="text")
            img_bytes = make_qr_dense(b64)
            st.image(img_bytes, caption="رمز QR ZATCA")
            st.download_button("⬇️ تحميل QR", img_bytes, "zatca_qr.png", "image/png")

# -----------------------------------------------------
# الصف الثاني: (Code128) + (PDF Metadata)
# -----------------------------------------------------
c3, c4 = st.columns(2)

with c3:
    st.header("🧾 مولّد باركود Code-128 (1.86 × 0.31 inch @ 600 DPI)")
    code128_val = st.text_input("أدخل الرقم/النص (Code-128)")
    if st.button("إنشاء Code-128"):
        s = sanitize(code128_val)
        if not s:
            st.error("أدخل نصًا صالحًا.")
        else:
            raw_png = render_barcode_png_bytes(s)
            final_png = resize_to_exact(raw_png, px_from_in(WIDTH_IN, DPI), px_from_in(HEIGHT_IN, DPI))
            st.image(final_png, caption=f"{WIDTH_IN}×{HEIGHT_IN} inch @ {DPI} DPI")
            st.download_button("⬇️ تحميل Code-128", final_png, "code128.png", "image/png")

with c4:
    st.header("📑 أداة تعديل بيانات PDF Metadata")
    up = st.file_uploader("قم بتحميل ملف PDF", type=["pdf"])
    if up:
        if "metadata" not in st.session_state:
            st.session_state.metadata = read_pdf_metadata(up)

        md = st.session_state.get("metadata", {})
        if md:
            # تهيئة مفاتيح session_state لكل الحقول مرة واحدة
            for k, v in md.items():
                if k not in st.session_state:
                    st.session_state[k] = v

            st.subheader("بيانات التعريف الحالية")
            auto_sync = st.checkbox("تحديث تلقائي ثنائي الاتجاه بين ModDate و CreationDate (أثناء الكتابة)", key="sync_dates", value=True)

            # --- مزامنة فورية قبل رسم الحقول (تجنّب خطأ Streamlit) ---
            # تعقب آخر قيم لتمييز الحقل الذي تغيّر
            if "md_last_creation" not in st.session_state:
                st.session_state.md_last_creation = st.session_state.get("/CreationDate", "")
            if "md_last_mod" not in st.session_state:
                st.session_state.md_last_mod = st.session_state.get("/ModDate", "")

            if auto_sync:
                cur_c = st.session_state.get("/CreationDate", "")
                cur_m = st.session_state.get("/ModDate", "")

                # إذا تغيّر CreationDate عن آخر قيمة، انسخه إلى ModDate
                if cur_c != st.session_state.md_last_creation:
                    st.session_state["/ModDate"] = cur_c
                    cur_m = cur_c

                # إذا تغيّر ModDate عن آخر قيمة، انسخه إلى CreationDate
                elif cur_m != st.session_state.md_last_mod:
                    st.session_state["/CreationDate"] = cur_m
                    cur_c = cur_m

                # حدّث "آخر قيمة" للحلقة القادمة
                st.session_state.md_last_creation = cur_c
                st.session_state.md_last_mod = cur_m

            # --- عرض كل الحقول (غير مرتبة) مع تفضيل ترتيب خاص للتاريخين ---
            order_first = ["/ModDate", "/CreationDate"]
            keys_ordered = order_first + [k for k in md.keys() if k not in order_first]

            updated = {}
            for k in keys_ordered:
                disp = k[1:] if k.startswith("/") else k
                val = st.text_input(disp, value=st.session_state.get(k, ""), key=k)
                updated[k] = val  # تُستخدم عند الحفظ

            if st.button("تحديث بيانات التعريف وحفظ الملف"):
                out_pdf = update_pdf_metadata(up, updated)
                if out_pdf:
                    st.success("تم التحديث بنجاح ✅")
                    st.download_button("تحميل الملف المعدّل", data=out_pdf, file_name=up.name, mime="application/pdf")
