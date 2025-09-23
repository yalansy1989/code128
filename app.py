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
/* عناوين ديناميكية */
h1, h2, h3 { text-align:center; font-weight:700; }
@media (prefers-color-scheme: light) { h1, h2, h3 { color:#046307 !important; } }
@media (prefers-color-scheme: dark)  { h1, h2, h3 { color:#ffffff !important; } }
.block-container { padding-top: 1.2rem; }
</style>
""", unsafe_allow_html=True)

st.title("💰 حاسبة الضريبة + مولّد QR (ZATCA) + Code128 + PDF Metadata")

# ---------------- أدوات مساعدة ----------------
def _clean_vat(v: str) -> str: return re.sub(r"\D", "", v or "")
def _fmt2(x: str) -> str:
    try: q = Decimal(x)
    except InvalidOperation: q = Decimal("0")
    return format(q.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")
def _iso_utc(d: date, t: time) -> str:
    dt = datetime.combine(d, t.replace(second=0, microsecond=0))
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def _tlv(tag: int, val: str) -> bytes:
    b = val.encode("utf-8"); return bytes([tag, len(b)]) + b
def build_zatca_base64(seller, vat, dt_iso, total, vat_s):
    return base64.b64encode(b"".join([
        _tlv(1,seller), _tlv(2,vat), _tlv(3,dt_iso), _tlv(4,total), _tlv(5,vat_s)
    ])).decode("ascii")

# ---------------- QR ----------------
def make_qr(b64: str) -> bytes:
    qr = qrcode.QRCode(version=14, error_correction=ERROR_CORRECT_M, box_size=2, border=4)
    qr.add_data(b64); qr.make(fit=False)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((640, 640), Image.NEAREST)
    out = BytesIO(); img.save(out, format="PNG")
    return out.getvalue()

# ---------------- Code128 ----------------
WIDTH_IN, HEIGHT_IN, DPI = 1.86, 0.31, 600
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
def sanitize(s): return re.sub(r"[^\x00-\x7F]", "", (s or "").translate(ARABIC_DIGITS))
def render_code128(data: str) -> bytes:
    code = Code128(data, writer=ImageWriter())
    buf = BytesIO()
    code.write(buf, {"write_text": False, "dpi": DPI, "module_height": HEIGHT_IN*25.4, "quiet_zone": 0})
    return buf.getvalue()
def resize_code128(png: bytes) -> bytes:
    with Image.open(BytesIO(png)) as im:
        im = im.resize((int(WIDTH_IN*DPI), int(HEIGHT_IN*DPI)), Image.NEAREST)
        out = BytesIO(); im.save(out, format="PNG", dpi=(DPI,DPI))
        return out.getvalue()

# ---------------- PDF Metadata ----------------
ALL_KEYS = ["/Title","/Author","/Subject","/Keywords","/Creator","/Producer","/CreationDate","/ModDate"]
def pdf_date_to_display_date(s):
    if not s: return ""
    if s.startswith("D:"): s=s[2:]
    m=re.match(r"^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})",s)
    if m:
        y,M,d,H,m_,s_=m.groups()
        try: return datetime(int(y),int(M),int(d),int(H),int(m_),int(s_)).strftime("%d/%m/%Y, %H:%M:%S")
        except: return s
    return s
def display_date_to_pdf_date(s):
    try: return datetime.strptime(s,"%d/%m/%Y, %H:%M:%S").strftime("D:%Y%m%d%H%M%S+03'00'")
    except: return s
def read_meta(f):
    f.seek(0); r=PdfReader(f); md=r.metadata or {}
    return {k:(pdf_date_to_display_date(md.get(k,"")) if k in ("/CreationDate","/ModDate") else md.get(k,"")) for k in ALL_KEYS}
def write_meta(f, new):
    f.seek(0); r=PdfReader(f); w=PdfWriter()
    for p in r.pages: w.add_page(p)
    final={}
    for k,v in new.items():
        final[k]=display_date_to_pdf_date(v) if k in ("/CreationDate","/ModDate") else v
    w.add_metadata(final); out=io.BytesIO(); w.write(out); out.seek(0); return out

# -----------------------------------------------------
# الصف الأول: (الحاسبة) + (مولد QR)
# -----------------------------------------------------
c1,c2=st.columns(2)
with c1:
    st.header("📊 حاسبة الضريبة")
    incl=st.number_input("المبلغ شامل الضريبة",0.0)
    rate=st.number_input("نسبة الضريبة %",1.0,100.0,15.0)
    if st.button("احسب"):
        before=incl/(1+rate/100)
        st.success(f"قبل الضريبة: {before:.2f} | الضريبة: {incl-before:.2f}")

with c2:
    st.header("🔖 مولّد QR")
    vat=st.text_input("الرقم الضريبي (15 رقم)")
    seller=st.text_input("اسم البائع")
    total=st.text_input("الإجمالي")
    tax=st.text_input("الضريبة")
    d=st.date_input("التاريخ",date.today())
    t=st.time_input("الوقت",datetime.now().time().replace(second=0,microsecond=0))
    if st.button("إنشاء QR"):
        vat=_clean_vat(vat)
        if len(vat)!=15: st.error("خطأ بالرقم الضريبي")
        else:
            b64=build_zatca_base64(seller,vat,_iso_utc(d,t),_fmt2(total),_fmt2(tax))
            img=make_qr(b64)
            st.image(img); st.download_button("تحميل",img,"qr.png","image/png")

# -----------------------------------------------------
# الصف الثاني: (Code128) + (Metadata)
# -----------------------------------------------------
c3,c4=st.columns(2)
with c3:
    st.header("🧾 Code128")
    val=st.text_input("النص")
    if st.button("إنشاء Code128"):
        s=sanitize(val)
        if not s: st.error("أدخل قيمة")
        else:
            raw=render_code128(s); final=resize_code128(raw)
            st.image(final); st.download_button("تحميل",final,"code128.png","image/png")

with c4:
    st.header("📑 Metadata PDF")
    f=st.file_uploader("تحميل PDF",type=["pdf"])
    if f:
        if "meta" not in st.session_state: st.session_state.meta=read_meta(f)
        auto=st.checkbox("تحديث تلقائي بين ModDate و CreationDate",True)
        updated={}
        for k in ALL_KEYS:
            disp=k[1:]
            val=st.session_state.meta.get(k,"")
            new=st.text_input(disp,val,key=k)
            updated[k]=new
        # مزامنة ديناميكية ثنائية الاتجاه
        if auto:
            if updated["/CreationDate"]!=st.session_state.meta["/CreationDate"]:
                updated["/ModDate"]=updated["/CreationDate"]
            elif updated["/ModDate"]!=st.session_state.meta["/ModDate"]:
                updated["/CreationDate"]=updated["/ModDate"]
        st.session_state.meta=updated
        if st.button("حفظ Metadata"):
            out=write_meta(f,updated)
            st.download_button("تحميل المعدل",out,f.name,"application/pdf")
