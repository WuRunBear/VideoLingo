import streamlit as st
import os, sys
from core.st_utils.imports_and_utils import *
from core import *

# SET PATH
current_dir = os.path.dirname(os.path.abspath(__file__))
os.environ['PATH'] += os.pathsep + current_dir
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(page_title="VideoLingo", page_icon="docs/logo.svg")

SUB_VIDEO = "static/output/output_sub.mp4"
DUB_VIDEO = "static/output/output_dub.mp4"

def text_processing_section():
    st.header(t("b. Translate and Generate Subtitles"))
    with st.container(border=True):
        st.markdown(f"""
        <p style='font-size: 20px;'>
        {t("This stage includes the following steps:")}
        <p style='font-size: 20px;'>
            1. {t("WhisperX word-level transcription")}<br>
            2. {t("Sentence segmentation using NLP and LLM")}<br>
            3. {t("Summarization and multi-step translation")}<br>
            4. {t("Cutting and aligning long subtitles")}<br>
            5. {t("Generating timeline and subtitles")}<br>
            6. {t("Merging subtitles into the video")}
        """, unsafe_allow_html=True)

        if not os.path.exists(SUB_VIDEO):
            if st.button(t("Start Processing Subtitles"), key="text_processing_button"):
                process_text()
                st.rerun()
        else:
            if load_key("burn_subtitles"):
                st.video(SUB_VIDEO)
            download_subtitle_zip_button(text=t("Download All Srt Files"))
            
            if os.path.exists("static/output/log/translation_results.xlsx"):
                st.download_button(
                    label="📥 " + t("Download Translation Results"),
                    data=open("static/output/log/translation_results.xlsx", "rb"),
                    file_name="translation_results.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            
            if st.button(t("Archive to 'history'"), key="cleanup_in_text_processing"):
                cleanup()
                st.rerun()
            return True

def process_text():
    with st.spinner(t("Using Whisper for transcription...")):
        _2_asr.transcribe()
    with st.spinner(t("Splitting long sentences...")):  
        _3_1_split_nlp.split_by_spacy()
        _3_2_split_meaning.split_sentences_by_meaning()
    with st.spinner(t("Summarizing and translating...")):
        _4_1_summarize.get_summary()
        if load_key("pause_before_translate"):
            input(t("⚠️ PAUSE_BEFORE_TRANSLATE. Go to `static/output/log/terminology.json` to edit terminology. Then press ENTER to continue..."))
        _4_2_translate.translate_all()
    with st.spinner(t("Processing and aligning subtitles...")): 
        _5_split_sub.split_for_sub_main()
        _6_gen_sub.align_timestamp_main()
    with st.spinner(t("Merging subtitles to video...")):
        _7_sub_into_vid.merge_subtitles_to_video()
    
    st.success(t("Subtitle processing complete! 🎉"))
    st.balloons()

def audio_processing_section():
    st.header(t("c. Dubbing"))
    with st.container(border=True):
        st.markdown(f"""
        <p style='font-size: 20px;'>
        {t("This stage includes the following steps:")}
        <p style='font-size: 20px;'>
            1. {t("Generate audio tasks and chunks")}<br>
            2. {t("Extract reference audio")}<br>
            3. {t("Generate and merge audio files")}<br>
            4. {t("Merge final audio into video")}
        """, unsafe_allow_html=True)
        if not os.path.exists(DUB_VIDEO):
            if st.button(t("Start Audio Processing"), key="audio_processing_button"):
                process_audio()
                st.rerun()
        else:
            st.success(t("Audio processing is complete! You can check the audio files in the `static/output` folder."))
            if load_key("burn_subtitles"):
                st.video(DUB_VIDEO) 
            
            if os.path.exists("static/output/audio/tts_tasks.xlsx"):
                st.download_button(
                    label="📥 " + t("Download Audio Tasks"),
                    data=open("static/output/audio/tts_tasks.xlsx", "rb"),
                    file_name="tts_tasks.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

            if st.button(t("Delete dubbing files"), key="delete_dubbing_files"):
                delete_dubbing_files()
                st.rerun()
            if st.button(t("Archive to 'history'"), key="cleanup_in_audio_processing"):
                cleanup()
                st.rerun()

def process_audio():
    with st.spinner(t("Generate audio tasks")): 
        _8_1_audio_task.gen_audio_task_main()
        _8_2_dub_chunks.gen_dub_chunks()
    with st.spinner(t("Extract refer audio")):
        _9_refer_audio.extract_refer_audio_main()
    with st.spinner(t("Generate all audio")):
        _10_gen_audio.gen_audio()
    with st.spinner(t("Merge full audio")):
        _11_merge_audio.merge_full_audio()
    with st.spinner(t("Merge dubbing to the video")):
        _12_dub_to_vid.merge_video_audio()
    
    st.success(t("Audio processing complete! 🎇"))
    st.balloons()

def render_directory(dir_path, base_dir, depth=0):
    """Recursively render directories using st.expander"""
    import urllib.parse
    
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

def file_explorer_section():
    st.header(t("File Explorer"))
    with st.container(border=True):
        from pathlib import Path
        
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

def main():
    logo_col, _ = st.columns([1,1])
    with logo_col:
        st.image("docs/logo.png", width="stretch")
    st.markdown(button_style, unsafe_allow_html=True)
    welcome_text = t("Hello, welcome to VideoLingo. If you encounter any issues, feel free to get instant answers with our Free QA Agent <a href=\"https://share.fastgpt.in/chat/share?shareId=066w11n3r9aq6879r4z0v9rh\" target=\"_blank\">here</a>! You can also try out our SaaS website at <a href=\"https://videolingo.io\" target=\"_blank\">videolingo.io</a> for free!")
    st.markdown(f"<p style='font-size: 20px; color: #808080;'>{welcome_text}</p>", unsafe_allow_html=True)
    # add settings
    with st.sidebar:
        page_setting()
        st.markdown(give_star_button, unsafe_allow_html=True)
    download_video_section()
    text_processing_section()
    audio_processing_section()
    file_explorer_section()

if __name__ == "__main__":
    main()
