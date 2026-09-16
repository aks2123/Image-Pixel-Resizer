import io
import os
import zipfile
from PIL import Image
import streamlit as st

# -----------------------------------------------------------------------------
# Page Configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="PixelCraft - Image & DPI Resizer",
    page_icon="🖼️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #6c757d;
        margin-bottom: 1.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Helper Functions & Constants
# -----------------------------------------------------------------------------
RESAMPLE_FILTERS = {
    "Lanczos (High Quality / Downscaling)": Image.Resampling.LANCZOS,
    "Bicubic (Smooth / General)": Image.Resampling.BICUBIC,
    "Bilinear (Fast)": Image.Resampling.BILINEAR,
    "Nearest Neighbor (Pixel Art / Crisp)": Image.Resampling.NEAREST,
}

DIMENSION_PRESETS = {
    "Social: Instagram Square (1080 x 1080)": (1080, 1080),
    "Social: Instagram Story / Reel (1080 x 1920)": (1080, 1920),
    "Social: Twitter / X Post (1200 x 675)": (1200, 675),
    "Social: YouTube Thumbnail (1280 x 720)": (1280, 720),
    "Display: Full HD (1920 x 1080)": (1920, 1080),
    "Display: 4K UHD (3840 x 2160)": (3840, 2160),
    "Web: Thumbnail (150 x 150)": (150, 150),
    "Web: Avatar / Icon (64 x 64)": (64, 64),
}

DPI_PRESETS = {
    "72 DPI — Screen / Web standard": 72,
    "96 DPI — Windows display default": 96,
    "150 DPI — Medium quality print / draft": 150,
    "300 DPI — High quality print standard (Press)": 300,
    "600 DPI — Ultra fine art print": 600,
    "Custom DPI": -1,
}


def format_bytes(size_in_bytes: int) -> str:
    """Format bytes into readable format (KB, MB)."""
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    elif size_in_bytes < 1024 * 1024:
        return f"{size_in_bytes / 1024:.1f} KB"
    else:
        return f"{size_in_bytes / (1024 * 1024):.2f} MB"


def get_image_dpi(image: Image.Image) -> tuple[int, int]:
    """Retrieve existing DPI from image metadata if available."""
    dpi_info = image.info.get("dpi")
    if dpi_info:
        try:
            return int(round(dpi_info[0])), int(round(dpi_info[1]))
        except Exception:
            pass
    return (72, 72)


def calculate_physical_size(width_px: int, height_px: int, dpi: int) -> str:
    """Calculate print size in inches and centimeters."""
    if dpi <= 0:
        return "N/A"
    w_in = width_px / dpi
    h_in = height_px / dpi
    w_cm = w_in * 2.54
    h_cm = h_in * 2.54
    return f'{w_in:.2f}" × {h_in:.2f}" ({w_cm:.1f} × {h_cm:.1f} cm)'


def resize_image(image: Image.Image, target_size: tuple[int, int], resample_filter) -> Image.Image:
    """Resize image using specified resample filter."""
    return image.resize(target_size, resample=resample_filter)


def prepare_download_buffer(image: Image.Image, output_format: str, quality: int, dpi: int) -> io.BytesIO:
    """Export PIL image to byte buffer in desired format with DPI metadata."""
    buf = io.BytesIO()
    save_format = output_format.upper()

    if save_format in ["JPEG", "JPG"] and image.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", image.size, (255, 255, 255))
        if image.mode == "P":
            image = image.convert("RGBA")
        background.paste(image, mask=image.split()[-1])
        img_to_save = background
    else:
        img_to_save = image

    save_kwargs = {}
    if save_format in ["JPEG", "JPG", "WEBP"]:
        save_kwargs["quality"] = quality
    if save_format == "PNG":
        save_kwargs["optimize"] = True

    if dpi > 0:
        save_kwargs["dpi"] = (dpi, dpi)

    img_to_save.save(buf, format=save_format, **save_kwargs)
    buf.seek(0)
    return buf


# -----------------------------------------------------------------------------
# Main Application
# -----------------------------------------------------------------------------
st.markdown('<div class="main-header">🖼️ Image Pixel & DPI Resizer</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Upload images to customize pixel dimensions, adjust print DPI, preview changes, and download.</div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("⚙️ Resize Controls")

    mode = st.radio(
        "Pixel Dimension Mode",
        options=["Exact Dimensions (Width × Height)", "Percentage Scaling (%)", "Presets"],
        index=0,
    )

    st.markdown("---")
    st.subheader("🖨️ DPI (Print Resolution)")

    dpi_choice = st.selectbox("DPI Preset", list(DPI_PRESETS.keys()), index=3)  # Default: 300 DPI
    if DPI_PRESETS[dpi_choice] == -1:
        target_dpi = st.number_input("Enter Custom DPI", min_value=10, max_value=2400, value=300, step=10)
    else:
        target_dpi = DPI_PRESETS[dpi_choice]

    st.caption(f"Target DPI: **{target_dpi} dots/inch**")

    st.markdown("---")
    st.subheader("🎨 Output Format & Quality")
    output_format = st.selectbox("Format", ["Original", "PNG", "JPEG", "WEBP"], index=0)
    quality = st.slider("Quality (JPEG / WEBP)", min_value=10, max_value=100, value=92, step=1)

    resample_name = st.selectbox("Resampling Filter", list(RESAMPLE_FILTERS.keys()), index=0)
    chosen_filter = RESAMPLE_FILTERS[resample_name]

uploaded_files = st.file_uploader(
    "Choose an image or multiple images...",
    type=["png", "jpg", "jpeg", "webp", "bmp", "tiff"],
    accept_multiple_files=True,
)

if not uploaded_files:
    st.info("👆 Please upload one or more images to get started.")
    st.stop()

# -----------------------------------------------------------------------------
# Single Image Processing
# -----------------------------------------------------------------------------
if len(uploaded_files) == 1:
    uploaded_file = uploaded_files[0]
    original_bytes = uploaded_file.getvalue()
    original_size_bytes = len(original_bytes)

    image = Image.open(io.BytesIO(original_bytes))
    orig_w, orig_h = image.size
    orig_dpi_x, orig_dpi_y = get_image_dpi(image)
    orig_format = (image.format or "PNG").upper()
    final_format = orig_format if output_format == "Original" else output_format

    with st.sidebar:
        st.markdown("---")
        st.subheader("📐 Target Dimensions")

        if mode == "Exact Dimensions (Width × Height)":
            maintain_aspect = st.checkbox("Lock Aspect Ratio", value=True)
            col_w, col_h = st.columns(2)
            with col_w:
                target_w = st.number_input("Width (px)", min_value=1, max_value=20000, value=orig_w, step=10)
            with col_h:
                if maintain_aspect:
                    calculated_h = max(1, int(round(target_w * (orig_h / orig_w))))
                    target_h = st.number_input(
                        "Height (px)",
                        min_value=1,
                        max_value=20000,
                        value=calculated_h,
                        disabled=True,
                    )
                else:
                    target_h = st.number_input("Height (px)", min_value=1, max_value=20000, value=orig_h, step=10)

        elif mode == "Percentage Scaling (%)":
            scale_percent = st.slider("Scale Percentage", min_value=1, max_value=500, value=100, step=1)
            target_w = max(1, int(round(orig_w * (scale_percent / 100.0))))
            target_h = max(1, int(round(orig_h * (scale_percent / 100.0))))
            st.caption(f"New Dimensions: **{target_w} × {target_h} px**")

        else:  # Presets
            preset_choice = st.selectbox("Dimension Preset", list(DIMENSION_PRESETS.keys()))
            target_w, target_h = DIMENSION_PRESETS[preset_choice]
            st.caption(f"Preset Dimensions: **{target_w} × {target_h} px**")

    # Resize & Prepare Buffer
    resized_img = resize_image(image, (target_w, target_h), chosen_filter)
    download_buf = prepare_download_buffer(resized_img, final_format, quality, target_dpi)
    new_size_bytes = len(download_buf.getvalue())
    size_diff_pct = ((new_size_bytes - original_size_bytes) / original_size_bytes) * 100

    # Physical Print Sizes
    orig_print_size = calculate_physical_size(orig_w, orig_h, orig_dpi_x)
    new_print_size = calculate_physical_size(target_w, target_h, target_dpi)

    # Preview & Comparisons (using use_column_width=True for stlite compatibility)
    st.markdown("### 🔍 Image Preview & Details")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Original Image")
        st.image(image, use_column_width=True)
        st.markdown(
            f"""
            - **Dimensions:** `{orig_w} × {orig_h} px`
            - **Resolution (DPI):** `{orig_dpi_x} × {orig_dpi_y} DPI`
            - **Print Size:** `{orig_print_size}`
            - **Format:** `{orig_format}`
            - **File Size:** `{format_bytes(original_size_bytes)}`
            """
        )

    with col2:
        st.subheader("Resized & Adjusted Image")
        st.image(resized_img)
        diff_label = f"({size_diff_pct:+.1f}%)" if size_diff_pct != 0 else ""
        st.markdown(
            f"""
            - **Dimensions:** `{target_w} × {target_h} px`
            - **Resolution (DPI):** `{target_dpi} × {target_dpi} DPI`
            - **Print Size:** `{new_print_size}`
            - **Format:** `{final_format}`
            - **File Size:** `{format_bytes(new_size_bytes)}` {diff_label}
            """
        )

    # Download Button
    base_name = os.path.splitext(uploaded_file.name)[0]
    out_ext = final_format.lower()
    if out_ext == "jpeg":
        out_ext = "jpg"
    download_filename = f"{base_name}_{target_w}x{target_h}_{target_dpi}dpi.{out_ext}"

    st.markdown("---")
    col_d1, col_d2, col_d3 = st.columns([1, 2, 1])
    with col_d2:
        st.download_button(
            label=f"⬇️ Download Image ({format_bytes(new_size_bytes)})",
            data=download_buf,
            file_name=download_filename,
            mime=f"image/{out_ext}",
            use_container_width=True,
            type="primary",
        )

# -----------------------------------------------------------------------------
# Batch Mode Processing
# -----------------------------------------------------------------------------
else:
    st.markdown(f"### 📦 Batch Processing ({len(uploaded_files)} images)")

    with st.sidebar:
        st.markdown("---")
        st.subheader("📐 Batch Resize Settings")
        if mode == "Percentage Scaling (%)":
            scale_percent = st.slider("Scale Percentage", min_value=1, max_value=500, value=100, step=1)
        elif mode == "Presets":
            preset_choice = st.selectbox("Preset Target", list(DIMENSION_PRESETS.keys()))
            target_preset_w, target_preset_h = DIMENSION_PRESETS[preset_choice]
        else:
            st.info("In batch mode, percentage scaling is recommended to preserve aspect ratios.")
            scale_percent = st.slider("Scale Percentage (%)", min_value=1, max_value=500, value=100, step=1)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        progress_bar = st.progress(0, text="Resizing images with DPI...")

        for idx, file in enumerate(uploaded_files):
            file_bytes = file.getvalue()
            pil_img = Image.open(io.BytesIO(file_bytes))
            orig_w, orig_h = pil_img.size
            orig_fmt = (pil_img.format or "PNG").upper()
            target_fmt = orig_fmt if output_format == "Original" else output_format

            if mode == "Presets":
                tw, th = target_preset_w, target_preset_h
            else:
                tw = max(1, int(round(orig_w * (scale_percent / 100.0))))
                th = max(1, int(round(orig_h * (scale_percent / 100.0))))

            resized = resize_image(pil_img, (tw, th), chosen_filter)
            img_buf = prepare_download_buffer(resized, target_fmt, quality, target_dpi)

            base_name = os.path.splitext(file.name)[0]
            ext = target_fmt.lower()
            if ext == "jpeg":
                ext = "jpg"
            out_name = f"{base_name}_{tw}x{th}_{target_dpi}dpi.{ext}"

            zip_file.writestr(out_name, img_buf.getvalue())
            progress_bar.progress((idx + 1) / len(uploaded_files), text=f"Processed {idx + 1}/{len(uploaded_files)}")

    zip_buffer.seek(0)
    st.success("✅ All batch images resized with target DPI!")

    st.download_button(
        label=f"⬇️ Download All Resized Images (.ZIP - {format_bytes(len(zip_buffer.getvalue()))})",
        data=zip_buffer,
        file_name=f"resized_{target_dpi}dpi_images.zip",
        mime="application/zip",
        use_container_width=True,
        type="primary",
    )
