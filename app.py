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

# ================= إعداد عام + تنسيق =================
st.set_page_config(page_title="حاسبة + ZATCA + Code128 + PDF Metadata", page_icon="💰", layout="wide")

# إضافة CSS للتصميم العصري مع الأيقونات التفاعلية
st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
    /* التصميم العام */
    :root {
        --primary: #046307;
        --secondary: #2a9d8f;
        --accent: #e9c46a;
        --dark: #264653;
        --light: #f8f9fa;
        --shadow: 0 4px 12px rgba(0,0,0,0.1);
        --transition: all 0.3s ease;
    }
    
    body {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        color: var(--dark);
    }
    
    .main-header {
        background: linear-gradient(90deg, var(--primary), var(--secondary));
        padding: 1.5rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        box-shadow: var(--shadow);
        text-align: center;
        color: white;
        position: relative;
        overflow: hidden;
    }
    
    .main-header::before {
        content: "";
        position: absolute;
        top: -50%;
        right: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(255,255,255,0.2) 0%, rgba(255,255,255,0) 70%);
        transform: rotate(45deg);
        z-index: 1;
    }
    
    .main-header h1 {
        font-size: 2.5rem;
        margin: 0;
        position: relative;
        z-index: 2;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
    }
    
    .main-header .subtitle {
        font-size: 1.2rem;
        margin-top: 0.5rem;
        opacity: 0.9;
        position: relative;
        z-index: 2;
    }
    
    h1, h2, h3 {
        text-align: center;
        font-weight: 700;
        color: var(--primary);
        margin-bottom: 1.5rem;
        position: relative;
    }
    
    h1::after, h2::after, h3::after {
        content: "";
        position: absolute;
        bottom: -10px;
        left: 50%;
        transform: translateX(-50%);
        width: 80px;
        height: 3px;
        background: var(--accent);
        border-radius: 3px;
    }
    
    .block-container {
        padding-top: 1rem;
    }
    
    /* تصميم البطاقات */
    .card {
        background: white;
        border-radius: 15px;
        padding: 1.5rem;
        box-shadow: var(--shadow);
        margin-bottom: 1.5rem;
        transition: var(--transition);
        position: relative;
        overflow: hidden;
    }
    
    .card::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        width: 5px;
        height: 100%;
        background: var(--secondary);
        transition: var(--transition);
    }
    
    .card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.15);
    }
    
    .card:hover::before {
        width: 100%;
        opacity: 0.1;
    }
    
    /* تصميم الأزرار */
    div[data-testid="stButton"] > button {
        background: linear-gradient(90deg, var(--primary), var(--secondary));
        color: white;
        border: none;
        border-radius: 50px;
        padding: 0.6rem 1.5rem;
        font-weight: 600;
        transition: var(--transition);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        position: relative;
        overflow: hidden;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
    }
    
    div[data-testid="stButton"] > button::before {
        content: "";
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: rgba(255,255,255,0.2);
        transition: var(--transition);
    }
    
    div[data-testid="stButton"] > button:hover::before {
        left: 100%;
    }
    
    div[data-testid="stButton"] > button:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
    }
    
    div[data-testid="stButton"] > button:active {
        transform: translateY(1px);
    }
    
    /* تصميم حقول الإدخال */
    div[data-testid="stTextInput"] > div > div > input {
        border-radius: 10px;
        border: 2px solid #e0e0e0;
        padding: 0.8rem 1rem;
        transition: var(--transition);
        font-size: 1rem;
    }
    
    div[data-testid="stTextInput"] > div > div > input:focus {
        border-color: var(--secondary);
        box-shadow: 0 0 0 3px rgba(42, 157, 143, 0.2);
    }
    
    div[data-testid="stNumberInput"] > div > div > input {
        border-radius: 10px;
        border: 2px solid #e0e0e0;
        padding: 0.8rem 1rem;
        transition: var(--transition);
        font-size: 1rem;
    }
    
    div[data-testid="stNumberInput"] > div > div > input:focus {
        border-color: var(--secondary);
        box-shadow: 0 0 0 3px rgba(42, 157, 143, 0.2);
    }
    
    div[data-testid="stDateInput"] > div > div > input {
        border-radius: 10px;
        border: 2px solid #e0e0e0;
        padding: 0.8rem 1rem;
        transition: var(--transition);
        font-size: 1rem;
    }
    
    div[data-testid="stDateInput"] > div > div > input:focus {
        border-color: var(--secondary);
        box-shadow: 0 0 0 3px rgba(42, 157, 143, 0.2);
    }
    
    div[data-testid="stTimeInput"] > div > div > input {
        border-radius: 10px;
        border: 2px solid #e0e0e0;
        padding: 0.8rem 1rem;
        transition: var(--transition);
        font-size: 1rem;
    }
    
    div[data-testid="stTimeInput"] > div > div > input:focus {
        border-color: var(--secondary);
        box-shadow: 0 0 0 3px rgba(42, 157, 143, 0.2);
    }
    
    /* تصميم الأيقونات التفاعلية */
    .icon-container {
        display: flex;
        justify-content: center;
        margin: 1.5rem 0;
    }
    
    .icon-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        margin: 0 1.5rem;
        cursor: pointer;
        transition: var(--transition);
    }
    
    .icon-item:hover {
        transform: translateY(-5px);
    }
    
    .icon-item i {
        font-size: 2.5rem;
        color: var(--primary);
        margin-bottom: 0.5rem;
        transition: var(--transition);
    }
    
    .icon-item:hover i {
        color: var(--secondary);
        transform: scale(1.2);
    }
    
    .icon-item span {
        font-size: 0.9rem;
        font-weight: 600;
        color: var(--dark);
    }
    
    /* تصميم رسائل النجاح والخطأ */
    div[data-testid="stException"] {
        background-color: #ffebee;
        border-left: 5px solid #f44336;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    
    div[data-testid="stSuccess"] {
        background-color: #e8f5e9;
        border-left: 5px solid #4caf50;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    
    /* تصميم شريط التقدم */
    .progress-container {
        height: 8px;
        background: #e0e0e0;
        border-radius: 5px;
        margin: 1.5rem 0;
        overflow: hidden;
    }
    
    .progress-bar {
        height: 100%;
        background: linear-gradient(90deg, var(--primary), var(--secondary));
        border-radius: 5px;
        width: 0%;
        transition: width 1s ease-in-out;
    }
    
    /* تصميم عناصر التبويب */
    .tab-container {
        display: flex;
        justify-content: center;
        margin-bottom: 2rem;
    }
    
    .tab-item {
        padding: 0.8rem 1.5rem;
        margin: 0 0.5rem;
        background: white;
        border-radius: 50px;
        cursor: pointer;
        transition: var(--transition);
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        font-weight: 600;
        color: var(--dark);
    }
    
    .tab-item:hover {
        background: var(--secondary);
        color: white;
        transform: translateY(-3px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    
    .tab-item.active {
        background: var(--primary);
        color: white;
    }
    
    /* تصميم الصور */
    .image-container {
        display: flex;
        justify-content: center;
        margin: 1.5rem 0;
    }
    
    .image-container img {
        max-width: 100%;
        border-radius: 10px;
        box-shadow: var(--shadow);
        transition: var(--transition);
    }
    
    .image-container img:hover {
        transform: scale(1.02);
        box-shadow: 0 8px 16px rgba(0,0,0,0.2);
    }
    
    /* تصميم الفوتر */
    .footer {
        text-align: center;
        margin-top: 3rem;
        padding: 1.5rem;
        color: var(--dark);
        font-size: 0.9rem;
    }
    
    /* تصميم متجاوب */
    @media (max-width: 768px) {
        .main-header h1 {
            font-size: 2rem;
        }
        
        .icon-item {
            margin: 0 0.8rem;
        }
        
        .icon-item i {
            font-size: 2rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# إضافة الرأس مع الأيقونات التفاعلية
st.markdown("""
<div class="main-header">
    <h1><i class="fas fa-calculator"></i> تصميــم يـــوســـــــف الأنســـــــــي</h1>
    <div class="subtitle"><i class="fas fa-coins"></i> حاسبة الضريبة | <i class="fas fa-qrcode"></i> ZATCA QR | <i class="fas fa-barcode"></i> Code128 | <i class="fas fa-file-pdf"></i> PDF Metadata</div>
</div>
""", unsafe_allow_html=True)

# إضافة أيقونات تفاعلية
st.markdown("""
<div class="icon-container">
    <div class="icon-item">
        <i class="fas fa-calculator"></i>
        <span>حاسبة الضريبة</span>
    </div>
    <div class="icon-item">
        <i class="fas fa-qrcode"></i>
        <span>رمز QR</span>
    </div>
    <div class="icon-item">
        <i class="fas fa-barcode"></i>
        <span>باركود</span>
    </div>
    <div class="icon-item">
        <i class="fas fa-file-pdf"></i>
        <span>ملف PDF</span>
    </div>
</div>
""", unsafe_allow_html=True)

# إضافة شريط تقدم تفاعلي
st.markdown("""
<div class="progress-container">
    <div class="progress-bar" id="progressBar"></div>
</div>
""", unsafe_allow_html=True)

# ================= حالة افتراضية ثابتة (مرة واحدة فقط) =================
if "qr_initialized" not in st.session_state:
    now_time = datetime.now().time().replace(microsecond=0)
    st.session_state.update({
        "qr_total": "0.00",
        "qr_vat": "0.00",
        "qr_date": date.today(),
        "qr_time": now_time,
        "qr_vat_number": "",
        "qr_seller": "",
        # واجهة الوقت
        "qr_time_hm": now_time.replace(second=0),
        "qr_secs": now_time.second
    })
    st.session_state["qr_initialized"] = True

# ================= أدوات مشتركة =================
def _clean_vat(v: str) -> str: return re.sub(r"\D", "", v or "")

def _fmt2(x: str) -> str:
    try: q = Decimal(x)
    except InvalidOperation: q = Decimal("0")
    return format(q.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")

def _iso_utc(d: date, t: time) -> str:
    local_dt = datetime.combine(d, t.replace(microsecond=0))
    try:
        return local_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return local_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def _tlv(tag: int, val: str) -> bytes:
    b = val.encode("utf-8")
    if len(b) > 255: raise ValueError("TLV>255B")
    return bytes([tag, len(b)]) + b

def build_zatca_base64(seller, vat, dt_iso, total, vat_s):
    payload = b"".join([_tlv(1,seller), _tlv(2,vat), _tlv(3,dt_iso), _tlv(4,total), _tlv(5,vat_s)])
    return base64.b64encode(payload).decode("ascii")

# ================= QR (صورة كثيفة) =================
def make_qr(b64: str) -> bytes:
    qr = qrcode.QRCode(version=14, error_correction=ERROR_CORRECT_M, box_size=2, border=4)
    qr.add_data(b64); qr.make(fit=False)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((640, 640), Image.NEAREST)
    out = BytesIO(); img.save(out, format="PNG"); return out.getvalue()

# ================= Code128 (بدون هوامش وبالمقاس) =================
WIDTH_IN, HEIGHT_IN, DPI = 1.86, 0.34, 600
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

def sanitize(s: str) -> str:
    s = (s or "").translate(ARABIC_DIGITS)
    s = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]", "", s)
    return "".join(ch for ch in s if ord(ch) < 128).strip()

def render_code128(data: str) -> bytes:
    code = Code128(data, writer=ImageWriter())
    buf = BytesIO()
    code.write(buf, {
        "write_text": False,
        "dpi": int(DPI),
        "module_height": HEIGHT_IN * 25.4,  # mm
        "quiet_zone": 0.0,
        "background": "white",
        "foreground": "black",
    })
    return buf.getvalue()

def resize_code128(png_bytes: bytes) -> bytes:
    with Image.open(BytesIO(png_bytes)) as im:
        im = im.resize((int(WIDTH_IN*DPI), int(HEIGHT_IN*DPI)), Image.NEAREST)
        out = BytesIO(); im.save(out, format="PNG", dpi=(DPI, DPI))
        return out.getvalue()

# ================= PDF Metadata =================
BASE_KEYS = ["/ModDate","/CreationDate","/Producer","/Title","/Author","/Subject","/Keywords","/Creator"]

def pdf_date_to_display_date(s):
    if not s or not isinstance(s, str): return ""
    if s.startswith("D:"): s = s[2:]
    m = re.match(r"^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", s)
    if m:
        y,M,d,H,m_,sec = m.groups()
        try: return datetime(int(y),int(M),int(d),int(H),int(m_),int(sec)).strftime("%d/%m/%Y, %H:%M:%S")
        except: return s
    return s

def display_date_to_pdf_date(s):
    try: return datetime.strptime(s,"%d/%m/%Y, %H:%M:%S").strftime("D:%Y%m%d%H%M%S+03'00'")
    except: return s

def parse_display_dt(s: str):
    try:
        dt = datetime.strptime(s.strip(), "%d/%m/%Y, %H:%M:%S")
        return dt.date(), dt.time().replace(microsecond=0)
    except Exception:
        return None, None

def read_meta(file):
    file.seek(0); r = PdfReader(file); md = r.metadata or {}
    keys = BASE_KEYS + [k for k in md.keys() if k not in BASE_KEYS]
    out = {}
    for k in keys:
        v = md.get(k, "")
        out[k] = pdf_date_to_display_date(v) if k in ("/CreationDate","/ModDate") else v
    return out, keys

def write_meta(file, new_md):
    file.seek(0)
    r = PdfReader(file); w = PdfWriter()
    for p in r.pages: w.add_page(p)
    final = {}
    for k,v in new_md.items():
        final[k] = display_date_to_pdf_date(v) if k in ("/CreationDate","/ModDate") else v
    w.add_metadata(final)
    out = io.BytesIO(); w.write(out); out.seek(0); return out

# =========================================================
# الصف الأعلى: (يسار) الحاسبة  —  (يمين) Metadata
# =========================================================
c1, c2 = st.columns(2)

with c1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.header("📊 حاسبة الضريبة")
    total_incl = st.number_input("المبلغ شامل الضريبة", min_value=0.0, step=0.01)
    tax_rate   = st.number_input("نسبة الضريبة (%)", min_value=1.0, max_value=100.0, value=15.0, step=0.01)

    colA, colB = st.columns(2)
    with colA:
        if st.button("احسب الآن"):
            rate = tax_rate/100.0
            before = round(total_incl/(1+rate), 2)
            vat_amount = round(total_incl - before, 2)
            st.success(f"قبل الضريبة: {before:.2f} | الضريبة: {vat_amount:.2f}")
    with colB:
        if st.button("📤 إرسال القيم إلى مولّد QR"):
            # تحديث الإجمالي والضريبة فقط — بدون أي مساس بالتاريخ/الوقت
            rate = tax_rate/100.0 if tax_rate else 0.0
            before = round(total_incl/(1+rate), 2) if total_incl and rate else 0.0
            vat_amount = round(total_incl - before, 2) if total_incl and rate else 0.0
            st.session_state["qr_total"] = f"{total_incl:.2f}"
            st.session_state["qr_vat"]   = f"{vat_amount:.2f}"
            st.toast("تم إرسال الإجمالي والضريبة إلى قسم مولّد QR ✅")
    st.markdown('</div>', unsafe_allow_html=True)

with c2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.header("📑 Edit Metadata PDF")
    up = st.file_uploader("تحميل PDF", type=["pdf"])
    if up:
        if "meta_dict" not in st.session_state or st.session_state.get("_last_file_name") != up.name:
            meta, keys = read_meta(up)
            st.session_state.meta_keys = keys
            st.session_state.meta_dict = meta
            st.session_state._last_file_name = up.name
            for k, v in meta.items():
                if k not in st.session_state:
                    st.session_state[k] = v
            st.session_state.setdefault("_prev_creation", st.session_state.get("/CreationDate", ""))
            st.session_state.setdefault("_prev_mod",       st.session_state.get("/ModDate", ""))

        auto = st.checkbox("تحديث تلقائي ثنائي الاتجاه بين ModDate و CreationDate (أثناء الكتابة)", value=True, key="_auto_sync")

        # مزامنة فورية قبل رسم الحقول
        if auto:
            c_now = st.session_state.get("/CreationDate", "")
            m_now = st.session_state.get("/ModDate", "")
            pc = st.session_state.get("_prev_creation", c_now)
            pm = st.session_state.get("_prev_mod", m_now)
            if c_now != pc and m_now == pm:
                st.session_state["/ModDate"] = c_now; m_now = c_now
            elif m_now != pm and c_now == pc:
                st.session_state["/CreationDate"] = m_now; c_now = m_now
            st.session_state["_prev_creation"] = c_now
            st.session_state["_prev_mod"]      = m_now

        ordered = ["/ModDate","/CreationDate"] + [k for k in st.session_state.meta_keys if k not in ("/ModDate","/CreationDate")]
        updated = {}
        for k in ordered:
            label = k[1:] if k.startswith("/") else k
            st.text_input(label, key=k)
            updated[k] = st.session_state.get(k, "")

        if st.button("📨 إرسال CreationDate إلى مولّد QR"):
            cre = st.session_state.get("/CreationDate", "")
            d, t = parse_display_dt(cre)
            if d and t:
                # حفظ نهائي لقيم التاريخ/الوقت في مفاتيح QR (لن تُمس لاحقًا)
                st.session_state["qr_date"]    = d
                st.session_state["qr_time"]    = t
                st.session_state["qr_time_hm"] = t.replace(second=0)
                st.session_state["qr_secs"]    = t.second
                st.success("تم إرسال التاريخ والوقت إلى قسم مولّد QR ✅")
            else:
                st.error("صيغة CreationDate غير صحيحة. الصيغة: dd/mm/YYYY, HH:MM:SS")

        if st.button("حفظ Metadata"):
            out = write_meta(up, updated)
            st.download_button("تحميل الملف المعدّل", data=out, file_name=up.name, mime="application/pdf")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# الصف الأسفل: (يسار) Code128  —  (يمين) مولّد QR
# =========================================================
c3, c4 = st.columns(2)

with c3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.header("🧾 مولّد Code-128 (1.86 × 0.34 inch @ 600 DPI)")
    v = st.text_input("النص/الرقم")
    if st.button("إنشاء Code-128"):
        s = sanitize(v)
        if not s: st.error("أدخل قيمة.")
        else:
            raw = render_code128(s)
            final = resize_code128(raw)
            st.markdown('<div class="image-container">', unsafe_allow_html=True)
            st.image(final, caption=f"{WIDTH_IN}×{HEIGHT_IN} inch @ {DPI} DPI")
            st.markdown('</div>', unsafe_allow_html=True)
            st.download_button("⬇️ تحميل", final, "code128.png", "image/png")
    st.markdown('</div>', unsafe_allow_html=True)

with c4:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.header("🔖 مولّد QR (ZATCA)")

    st.text_input("الرقم الضريبي (15 رقم)", key="qr_vat_number")
    st.text_input("اسم البائع", key="qr_seller")
    st.text_input("الإجمالي (شامل)", key="qr_total")
    st.text_input("الضريبة", key="qr_vat")

    # واجهة الوقت: ساعة/دقيقة + ثوانٍ، ثم دمجها في qr_time
    hm_time = st.time_input("الوقت (ساعة:دقيقة)", key="qr_time_hm", value=st.session_state["qr_time_hm"], step=60)
    secs = st.number_input("الثواني", min_value=0, max_value=59, step=1, key="qr_secs", value=st.session_state["qr_secs"])
    st.session_state["qr_time"] = time(hm_time.hour, hm_time.minute, int(secs))
    st.caption(f"الوقت الحالي: {st.session_state['qr_time'].strftime('%H:%M:%S')}")

    st.date_input("التاريخ", key="qr_date", value=st.session_state["qr_date"])

    if st.button("إنشاء رمز QR"):
        vclean = _clean_vat(st.session_state["qr_vat_number"])
        if len(vclean) != 15:
            st.error("الرقم الضريبي يجب أن يكون 15 رقمًا.")
        else:
            iso = _iso_utc(st.session_state["qr_date"], st.session_state["qr_time"])
            b64 = build_zatca_base64(
                st.session_state["qr_seller"].strip(),
                vclean,
                iso,
                _fmt2(st.session_state["qr_total"]),
                _fmt2(st.session_state["qr_vat"])
            )
            st.code(b64, language="text")
            img = make_qr(b64)
            st.markdown('<div class="image-container">', unsafe_allow_html=True)
            st.image(img, caption="رمز QR ZATCA")
            st.markdown('</div>', unsafe_allow_html=True)
            st.download_button("⬇️ تحميل QR", img, "zatca_qr.png", "image/png")
    st.markdown('</div>', unsafe_allow_html=True)

# إضافة الفوتر
st.markdown("""
<div class="footer">
    <p>تصميم وتطوير: يوسف الأنسي © 2023 | جميع الحقوق محفوظة</p>
</div>
""", unsafe_allow_html=True)

# إضافة JavaScript للتفاعل
st.markdown("""
<script>
    // تحريك شريط التقدم
    document.addEventListener('DOMContentLoaded', function() {
        const progressBar = document.getElementById('progressBar');
        if (progressBar) {
            setTimeout(() => {
                progressBar.style.width = '100%';
            }, 500);
        }
        
        // تأثير التمرير السلس
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                document.querySelector(this.getAttribute('href')).scrollIntoView({
                    behavior: 'smooth'
                });
            });
        });
        
        // تأثير الظهور عند التمرير
        const observerOptions = {
            root: null,
            rootMargin: '0px',
            threshold: 0.1
        };
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = 1;
                    entry.target.style.transform = 'translateY(0)';
                }
            });
        }, observerOptions);
        
        document.querySelectorAll('.card').forEach(card => {
            card.style.opacity = 0;
            card.style.transform = 'translateY(20px)';
            card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
            observer.observe(card);
        });
    });
</script>
""", unsafe_allow_html=True)
