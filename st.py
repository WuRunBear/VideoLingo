import os, sys
import mimetypes

# Fix mime types for static serving in Linux
mimetypes.add_type('video/mp4', '.mp4')
mimetypes.add_type('video/webm', '.webm')
mimetypes.add_type('video/ogg', '.ogg')
mimetypes.add_type('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '.xlsx')
mimetypes.add_type('application/zip', '.zip')
mimetypes.add_type('text/plain', '.srt')
mimetypes.add_type('application/json', '.json')
mimetypes.add_type('audio/mpeg', '.mp3')
mimetypes.add_type('audio/wav', '.wav')
mimetypes.add_type('image/png', '.png')
mimetypes.add_type('image/jpeg', '.jpg')
mimetypes.add_type('image/svg+xml', '.svg')

import streamlit as st
from core.st_utils.imports_and_utils import *
from core import *

# SET PATH
current_dir = os.path.dirname(os.path.abspath(__file__))
os.environ['PATH'] += os.pathsep + current_dir
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(page_title="VideoLingo", page_icon="docs/logo.svg")

SUB_VIDEO = "static/output/output_sub.mp4"
DUB_VIDEO = "static/output/output_dub.mp4"

def sentence_segmentation_section():
    st.header(t("b. Sentence Segmentation"))
    with st.container(border=True):
        st.markdown(f"""
        <p style='font-size: 20px;'>
        {t("This stage extracts speech and splits it into sentences. You can manually edit the split result before translation.")}
        """, unsafe_allow_html=True)

        split_file = "static/output/log/split_by_meaning.txt"

        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button(t("Run Sentence Segmentation"), key="run_segmentation_btn"):
                with st.spinner(t("Using Whisper for transcription...")):
                    _2_asr.transcribe()
                with st.spinner(t("Splitting long sentences...")):
                    _3_1_split_nlp.split_by_spacy()
                    _3_2_split_meaning.split_sentences_by_meaning()
                st.session_state.segmentation_confirmed = False
                st.success(t("Sentence segmentation complete"))
                st.rerun()

        if os.path.exists(split_file):
            st.download_button(
                label="📥 " + t("Download split results"),
                data=open(split_file, "rb"),
                file_name="split_by_meaning.txt",
                mime="text/plain",
                use_container_width=True,
            )
            st.info(t("Manual step: edit `static/output/log/split_by_meaning.txt` if needed, then click the confirm button below to continue."))

            if st.button(t("I have confirmed the split results, continue to translation"), key="confirm_segmentation_btn"):
                st.session_state.segmentation_confirmed = True
                st.success(t("Confirmed. You can now run translation in step c."))
        else:
            st.warning(t("Split result file not found. Please run sentence segmentation first."))

def translation_and_subtitle_section():
    st.header(t("c. Translate and Generate Subtitles"))
    with st.container(border=True):
        st.markdown(f"""
        <p style='font-size: 20px;'>
        {t("This stage includes the following steps:")}
        <p style='font-size: 20px;'>
            1. {t("Summarization and multi-step translation")}<br>
            2. {t("Cutting and aligning long subtitles")}<br>
            3. {t("Generating timeline and subtitles")}<br>
            4. {t("Merging subtitles into the video")}
        """, unsafe_allow_html=True)

        if not os.path.exists(SUB_VIDEO):
            if not os.path.exists("static/output/log/split_by_meaning.txt"):
                st.info(t("Please finish step b (Sentence Segmentation) first."))
                return
            if not st.session_state.get("segmentation_confirmed", False):
                st.info(t("Please confirm the split results in step b before running translation."))
                return

            if st.button(t("Start Translation and Subtitle Generation"), key="translation_processing_button"):
                process_translation_and_subtitles()
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

def process_translation_and_subtitles():
    with st.spinner(t("Summarizing and translating...")):
        _4_1_summarize.get_summary()
        _4_2_translate.translate_all()
    with st.spinner(t("Processing and aligning subtitles...")): 
        _5_split_sub.split_for_sub_main()
        _6_gen_sub.align_timestamp_main()
    with st.spinner(t("Merging subtitles to video...")):
        _7_sub_into_vid.merge_subtitles_to_video()
    
    st.success(t("Subtitle processing complete! 🎉"))
    st.balloons()

def audio_processing_section():
    st.header(t("d. Dubbing"))
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

def main():
    logo_col, _ = st.columns([1,1])
    with logo_col:
        st.image("docs/logo.png", width="stretch")
    st.markdown(button_style, unsafe_allow_html=True)
    welcome_text = t("Hello, welcome to VideoLingo. If you encounter any issues, feel free to get instant answers with our Free QA Agent <a href=\"https://share.fastgpt.in/chat/share?shareId=066w11n3r9aq6879r4z0v9rh\" target=\"_blank\">here</a>! You can also try out our SaaS website at <a href=\"https://videolingo.io\" target=\"_blank\">videolingo.io</a> for free!")
    st.markdown(f"<p style='font-size: 20px; color: #808080;'>{welcome_text}</p>", unsafe_allow_html=True)
    
    # 提示用户文件浏览器已移至侧边栏
    st.info(t("💡 You can now access the File Explorer from the sidebar on the left."))
    
    # add settings
    with st.sidebar:
        page_setting()
        st.markdown(give_star_button, unsafe_allow_html=True)
    download_video_section()
    sentence_segmentation_section()
    translation_and_subtitle_section()
    audio_processing_section()

if __name__ == "__main__":
    main()
