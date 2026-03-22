import streamlit as st
import os
from core.utils.config_utils import load_key
import urllib.parse
from pathlib import Path

st.set_page_config(page_title="VideoLingo - File Explorer", page_icon="docs/logo.svg")

# Try to load translations, fallback to simple strings
try:
    from core.st_utils.imports_and_utils import t
except Exception:
    def t(text):
        return text

st.title(t("File Explorer"))

def render_directory(dir_path, base_dir, depth=0):
    """Recursively render directories using st.expander"""
    try:
        items = list(dir_path.iterdir())
        dirs = sorted([d for d in items if d.is_dir()])
        files = sorted([f for f in items if f.is_file()])
        
        # Render subdirectories
        for d in dirs:
            with st.expander(f"📁 {d.name}"):
                render_directory(d, base_dir, depth + 1)
                
        # Render files
        for f in files:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown(f"📄 {f.name}")
            with col2:
                try:
                    rel_path = f.relative_to("static")
                    url_path = urllib.parse.quote(str(rel_path).replace("\\", "/"))
                    file_url = f"/app/static/{url_path}"
                    
                    st.markdown(f'<a href="{file_url}" target="_blank"><button style="width: 100%; border-radius: 5px; padding: 0.25rem 0.5rem; background-color: transparent; border: 1px solid #ccc; color: inherit; cursor: pointer;">Download</button></a>', unsafe_allow_html=True)
                except ValueError:
                    st.write("N/A")
            with col3:
                if f.suffix.lower() in ['.mp4', '.webm', '.ogg', '.mp3', '.wav']:
                    if st.button("Preview", key=f"preview_{f}"):
                        st.session_state.preview_file = f
    except Exception as e:
        st.error(f"Error reading directory: {e}")

with st.container(border=True):
    # Define the base directory for exploration
    base_dir = Path("static")
    
    if base_dir.exists():
        render_directory(base_dir, base_dir)
    else:
        st.info("Directory not found or empty.")
        
    # Show preview if selected
    if "preview_file" in st.session_state and st.session_state.preview_file.exists():
        st.divider()
        st.subheader("Preview")
        preview_file = st.session_state.preview_file
        st.markdown(f"**{preview_file.name}**")
        
        if preview_file.suffix.lower() in ['.mp4', '.webm', '.ogg']:
            st.video(str(preview_file))
        elif preview_file.suffix.lower() in ['.mp3', '.wav']:
            st.audio(str(preview_file))
        
        if st.button("Close Preview", key="close_preview_btn"):
            del st.session_state.preview_file
            st.rerun()