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
from core.utils.models import _2_CLEANED_CHUNKS

# SET PATH
current_dir = os.path.dirname(os.path.abspath(__file__))
os.environ['PATH'] += os.pathsep + current_dir
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(page_title="VideoLingo", page_icon="docs/logo.svg")

SUB_VIDEO = "static/output/output_sub.mp4"
DUB_VIDEO = "static/output/output_dub.mp4"
SPEAKER_MAPPING_DRAFT = "static/output/log/speaker_mapping_draft.xlsx"
SPEAKER_MAPPING_LOCKED = "static/output/log/speaker_mapping_locked.xlsx"

def mapping_section():
    st.header("b. 句子与说话人确认")
    with st.container(border=True):
        st.markdown(f"""
        <p style='font-size: 20px;'>
        {t("This stage includes the following steps:")}
        <p style='font-size: 20px;'>
            1. {t("WhisperX word-level transcription")}<br>
            2. {t("Sentence segmentation using NLP and LLM")}<br>
            3. 生成 speaker_mapping_draft.xlsx（每行一句）<br>
            4. 手动拆分/合并与修正 speaker_id<br>
            5. 锁定后进入翻译与字幕生成
        """, unsafe_allow_html=True)

        if not os.path.exists(SPEAKER_MAPPING_LOCKED):
            if not os.path.exists(SPEAKER_MAPPING_DRAFT):
                if st.button("开始转写并生成草稿", key="mapping_generate_draft"):
                    process_asr_and_mapping_draft()
                    st.rerun()
            else:
                st.download_button(
                    label="📥 下载 speaker_mapping_draft.xlsx",
                    data=open(SPEAKER_MAPPING_DRAFT, "rb"),
                    file_name="speaker_mapping_draft.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                with st.form("mapping_upload_draft_form"):
                    uploaded = st.file_uploader(
                        "上传新的 speaker_mapping_draft.xlsx",
                        type=["xlsx"],
                        key="mapping_upload_draft"
                    )
                    save_uploaded = st.form_submit_button("保存上传的草稿", use_container_width=True)
                if save_uploaded:
                    if uploaded is None:
                        st.error("请先选择一个 xlsx 文件再保存。")
                    else:
                        os.makedirs(os.path.dirname(SPEAKER_MAPPING_DRAFT), exist_ok=True)
                        with open(SPEAKER_MAPPING_DRAFT, "wb") as f:
                            f.write(uploaded.getvalue())
                        st.success("已上传并替换 speaker_mapping_draft.xlsx")
                with st.form("upload_cleaned_chunks_form"):
                    uploaded_chunks = st.file_uploader(
                        "上传新的 cleaned_chunks.xlsx（覆盖词级时间）",
                        type=["xlsx"],
                        key="upload_cleaned_chunks"
                    )
                    save_chunks = st.form_submit_button("保存 cleaned_chunks.xlsx", use_container_width=True)
                if save_chunks:
                    if uploaded_chunks is None:
                        st.error("请先选择一个 xlsx 文件再保存。")
                    else:
                        os.makedirs(os.path.dirname(_2_CLEANED_CHUNKS), exist_ok=True)
                        with open(_2_CLEANED_CHUNKS, "wb") as f:
                            f.write(uploaded_chunks.getvalue())
                        st.success("已上传并替换 cleaned_chunks.xlsx")
                st.info("请对照视频编辑 speaker_mapping_draft.xlsx（拆分/合并/修正 speaker_id），完成后点击“锁定映射并继续”。")
                if st.button("锁定映射并继续", key="mapping_lock"):
                    _3_3_speaker_mapping.lock_speaker_mapping()
                    st.rerun()
        else:
            st.success("speaker_mapping_locked.xlsx 已就绪，可以开始翻译与字幕生成。")
            st.download_button(
                label="📥 下载 speaker_mapping_locked.xlsx",
                data=open(SPEAKER_MAPPING_LOCKED, "rb"),
                file_name="speaker_mapping_locked.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

def process_asr_and_mapping_draft():
    with st.spinner(t("Using Whisper for transcription...")):
        _2_asr.transcribe()
    with st.spinner(t("Splitting long sentences...")):
        _3_1_split_nlp.split_by_spacy()
        _3_2_split_meaning.split_sentences_by_meaning()
    with st.spinner("Generating speaker mapping draft..."):
        _3_3_speaker_mapping.generate_speaker_mapping_draft()

def translate_processing_section():
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

        if not os.path.exists(SPEAKER_MAPPING_LOCKED):
            st.warning("请先完成 b 阶段：句子与说话人确认。")
            return

        if not os.path.exists(SUB_VIDEO):
            if st.button(t("Start Processing Subtitles"), key="translate_processing_button"):
                process_translate_and_subtitles()
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

            if st.button(t("Archive to 'history'"), key="cleanup_in_translate_processing"):
                cleanup()
                st.rerun()
            return True

def process_translate_and_subtitles():
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
    mapping_section()
    translate_processing_section()
    audio_processing_section()

if __name__ == "__main__":
    main()
