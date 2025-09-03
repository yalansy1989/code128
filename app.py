import streamlit as st
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO

st.set_page_config(page_title="مولّد باركود Code128", page_icon="🔖", layout="centered")
st.title("🔖 مولّد باركود Code-128 (PNG عالي الدقّة)")

data = st.text_input("أدخل النص/الرقم لعمل باركود", "72626525252626625")

col1, col2 = st.columns(2)
with col1:
    dpi = st.slider("الدقّة (DPI)", 300, 1200, 600, step=100)
    quiet = st.number_input("الهامش (quiet_zone) بالملّيمتر", 1.0, 20.0, 6.0, step=0.5)
with col2:
    mw = st.number_input("عرض أصغر شريط (module_width) بالملّيمتر", 0.1, 1.0, 0.44, step=0.01)
    mh = st.number_input("ارتفاع الأشرطة (module_height) بالملّيمتر", 5.0, 100.0, 28.0, step=1.0)

def make_barcode_png(data: str, dpi: int, mw: float, mh: float, quiet: float) -> bytes:
    writer = ImageWriter()
    options = {
        "write_text": False,   # بدون الرقم أسفل الباركود
        "dpi": dpi,
        "module_width": mw,
        "module_height": mh,
        "quiet_zone": quiet,
        "background": "white",
        "foreground": "black",
    }
    code = Code128(data, writer=writer)
    buf = BytesIO()
    code.write(buf, options)
    return buf.getvalue()

if st.button("إنشاء الباركود"):
    if not data:
        st.error("اكتب أي نص/رقم أولاً.")
    else:
        png_bytes = make_barcode_png(data, dpi, mw, mh, quiet)
        st.image(png_bytes, caption="Code128", use_container_width=True)
        st.download_button("⬇️ تحميل كـ PNG", png_bytes, file_name="code128.png", mime="image/png")
