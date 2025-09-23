import streamlit as st
from datetime import date, datetime
import re, base64, io
from io import BytesIO
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import qrcode
from qrcode.constants import ERROR_CORRECT_M
from PIL import Image
from barcode import Code128
from barcode.writer import ImageWriter
from pypdf import PdfReader, PdfWriter

# ================= إعداد عام =================
st.set_page_config(page_title="حاسبة الضريبة + QR + Code128 + PDF", page_icon="💰", layout="wide")

# ================= CSS =================
st.markdown("""
    <style>
    body { background-color: #b8860b; }
    .card {
        background-color: #fdf6e3;
        padding: 20px;
        border-radius: 12px;
        margin: 10px;
    }
    h1, h2, h3 {
        text-align: center;
        font-weight: bold;
    }
    @media (prefers-color-scheme: dark) {
        h1, h2, h3 { color: white !important; }
    }
    @media (prefers-color-scheme: light) {
        h1, h2, h3 { color: #004d00 !important; }
    }
    .stButton > button {
        background-color: #228B22;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        padding: 8px 16px;
    }
    .stButton > button:hover { background-color: #006400; }
    </style>
""", unsafe_allow_html=True)

# ================= العنوان =================
st.markdown("<h1>حاسبة الضريبة + مولد QR + Code128 + PDF Metadata</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;'>برمجة يوسف الأنسي</p>", unsafe_allow_html=True)

# ================= دوال مساعدة =================
def _fmt2(x: str) -> str:
    try: q = Decimal(x)
    except InvalidOperation: q = Decimal("0")
    q = q.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return format(q, "f")

def _iso_utc(dt_date: date, dt_time) -> str:
    local_dt = datetime.combine(dt_date, dt_time.replace(second=0, microsecond=0))
    return local_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def _tlv(tag: int, value: str) -> bytes:
    vb = value.encode("utf-8")
    return bytes([tag, len(vb)]) + vb

def build_zatca_base64(seller: str, vat: str, dt_iso: str, total_s: str, vat_s: str) -> str:
    payload = b"".join([
        _tlv(1, seller), _tlv(2, vat), _tlv(3, dt_iso),
        _tlv(4, total_s), _tlv(5, vat_s),
    ])
    return base64.b64encode(payload).decode("ascii")

def make_qr_dense(b64_text: str, final_px: int = 300) -> bytes:
    qr = qrcode.QRCode(version=5, error_correction=ERROR_CORRECT_M, box_size=5, border=2)
    qr.add_data(b64_text); qr.make(fit=False)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((final_px, final_px), Image.NEAREST)
    out = BytesIO(); img.save(out, format="PNG")
    return out.getvalue()

# إعداد باركود Code128
WIDTH_IN, HEIGHT_IN, DPI = 1.86, 0.31, 600
def inches_to_mm(x): return float(x) * 25.4
def px_from_in(inches, dpi): return int(round(float(inches) * int(dpi)))
def render_barcode_png_bytes(data: str) -> bytes:
    writer = ImageWriter()
    opts = {"write_text": False, "dpi": int(DPI), "module_height": 15.0,
            "quiet_zone": 0.0, "background": "white", "foreground": "black"}
    code = Code128(data, writer=writer)
    buf = BytesIO(); code.write(buf, opts); buf.seek(0)
    img = Image.open(buf).convert("RGB")
    bbox = img.getbbox()
    if bbox: img = img.crop(bbox)
    target_w_px = px_from_in(WIDTH_IN, DPI)
    target_h_px = px_from_in(HEIGHT_IN, DPI)
    img = img.resize((target_w_px, target_h_px), Image.NEAREST)
    out = BytesIO(); img.save(out, format="PNG", dpi=(DPI, DPI))
    return out.getvalue()

# PDF Metadata Functions
def pdf_date_to_display_date(pdf_date_str):
    if not pdf_date_str or not isinstance(pdf_date_str, str): return ""
    if pdf_date_str.startswith("D:"): pdf_date_str = pdf_date_str[2:]
    match = re.match(r"^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", pdf_date_str)
    if match:
        y, m, d, H, M, S = match.groups()
        try: return datetime(int(y), int(m), int(d), int(H), int(M), int(S)).strftime("%d/%m/%Y, %H:%M:%S")
        except ValueError: return pdf_date_str
    return pdf_date_str

def display_date_to_pdf_date(display_date_str):
    if not display_date_str or not isinstance(display_date_str, str): return ""
    try:
        dt_object = datetime.strptime(display_date_str, "%d/%m/%Y, %H:%M:%S")
        return dt_object.strftime("D:%Y%m%d%H%M%S+03'00'")
    except ValueError:
        return display_date_str

def read_pdf_metadata(pdf_file):
    try:
        pdf_file.seek(0); reader = PdfReader(pdf_file); metadata = reader.metadata
        processed = {}
        if metadata:
            for k,v in metadata.items():
                processed[k] = pdf_date_to_display_date(v) if k in ['/ModDate','/CreationDate'] else v
        return processed
    except Exception as e:
        st.error(f"خطأ عند قراءة البيانات: {e}"); return None

def update_pdf_metadata(pdf_file, new_metadata):
    try:
        pdf_file.seek(0); reader = PdfReader(pdf_file); writer = PdfWriter()
        for page in reader.pages: writer.add_page(page)
        final_meta = {}
        for k,v in new_metadata.items():
            final_meta[k] = display_date_to_pdf_date(v) if k in ['/ModDate','/CreationDate'] else v
        writer.add_metadata(final_meta)
        output = io.BytesIO(); writer.write(output); output.seek(0)
        return output
    except Exception as e:
        st.error(f"خطأ عند تحديث البيانات: {e}"); return None

# ================= القسمين العلويين =================
col1, col2 = st.columns(2)

with col1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📊 حاسبة الضريبة")
    total_incl = st.number_input("المبلغ شامل الضريبة", min_value=0.0, step=0.01)
    tax_rate = st.number_input("نسبة الضريبة (%)", min_value=1.0, max_value=100.0, value=15.0, step=0.01)
    if st.button("احسب الآن"):
        rate = tax_rate / 100.0
        before_tax = round(total_incl / (1 + rate), 2)
        tax_amount = round(total_incl - before_tax, 2)
        st.success(f"السعر قبل الضريبة: {before_tax:.2f} | مبلغ الضريبة: {tax_amount:.2f}")
        st.session_state["qr_total"] = f"{total_incl:.2f}"
        st.session_state["qr_vat"]   = f"{tax_amount:.2f}"
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🔖 مولد رمز QR (ZATCA)")
    vat_number = st.text_input("الرقم الضريبي (15 رقم)")
    seller_name = st.text_input("اسم البائع")
    total_str = st.text_input("الإجمالي (شامل)", value=st.session_state.get("qr_total", "0.00"))
    vat_str   = st.text_input("الضريبة", value=st.session_state.get("qr_vat", "0.00"))
    d_val = st.date_input("التاريخ", value=date.today())
    t_val = st.time_input("الوقت", value=datetime.now().time().replace(second=0, microsecond=0))
    if st.button("إنشاء رمز QR"):
        iso = _iso_utc(d_val, t_val)
        b64 = build_zatca_base64(seller_name.strip(), vat_number.strip(), iso, _fmt2(total_str), _fmt2(vat_str))
        qr_png = make_qr_dense(b64)
        st.image(qr_png, caption="رمز QR ZATCA")
        st.download_button("⬇️ تحميل رمز QR", qr_png, file_name="zatca_qr.png", mime="image/png")
    st.markdown('</div>', unsafe_allow_html=True)

# ================= القسمين السفليين =================
col3, col4 = st.columns(2)

with col3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🧾 مولد باركود Code-128")
    code128_val = st.text_input("أدخل الرقم/النص (Code-128)")
    if st.button("إنشاء Code-128"):
        if not code128_val.strip(): st.error("أدخل نصًا صالحًا.")
        else:
            try:
                final_png = render_barcode_png_bytes(code128_val.strip())
                st.image(final_png, caption=f"{WIDTH_IN} × {HEIGHT_IN} inch @ {DPI} DPI")
                st.download_button("⬇️ تحميل Code-128", final_png, file_name="code128.png", mime="image/png")
                st.success("✅ تم إنشاء الباركود بالمقاسات الدقيقة.")
            except Exception as e:
                st.error(f"تعذر الإنشاء: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

with col4:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📝 أداة تعديل بيانات PDF Metadata")
    uploaded_file = st.file_uploader("قم بتحميل ملف PDF", type=["pdf"])
    if uploaded_file is not None:
        st.success("تم تحميل الملف بنجاح!")
        if "metadata" not in st.session_state:
            st.session_state.metadata = read_pdf_metadata(uploaded_file)
        if st.session_state.metadata:
            updated_metadata = {}
            for key, value in st.session_state.metadata.items():
                display_key = key[1:] if key.startswith("/") else key
                updated_metadata[key] = st.text_input(display_key, value=value, key=key)
            if st.button("تحديث بيانات PDF"):
                updated_pdf = update_pdf_metadata(uploaded_file, updated_metadata)
                if updated_pdf:
                    st.success("تم تحديث بيانات PDF بنجاح!")
                    st.download_button("تحميل الملف المعدل", data=updated_pdf, file_name=uploaded_file.name)
    st.markdown('</div>', unsafe_allow_html=True)
