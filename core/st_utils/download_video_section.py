import os
import re
import shutil
import subprocess
from time import sleep

import streamlit as st
import streamlit.components.v1 as components
from core._1_ytdlp import download_video_ytdlp, find_video_files
from core.utils import *
from translations.translations import translate as t

OUTPUT_DIR = "static/output"

def download_video_section():
    st.header(t("a. Download or Upload Video"))
    with st.container(border=True):
        try:
            video_file = find_video_files()
            st.video(video_file)
            video_name = os.path.basename(video_file)
            components.html(
                f"""
                <div style="display:flex; gap:8px; align-items:center; margin-top: 8px;">
                  <input id="vl_copy_link" style="flex:1; padding:8px; border:1px solid #ddd; border-radius:6px;"
                         value="" readonly />
                  <button id="vl_copy_btn" style="padding:8px 12px; border:1px solid #ddd; border-radius:6px; background:white; cursor:pointer;">
                    复制链接
                  </button>
                </div>
                <div id="vl_copy_msg" style="margin-top:6px; font-size:12px; color:#666;"></div>
                <script>
                  const fileName = {video_name!r};
                  let origin = "null";
                  try {{
                    origin = new URL(document.baseURI).origin;
                  }} catch (e) {{
                    origin = window.location.origin;
                  }}
                  const link = `${{origin}}/staticfile/output/${{encodeURIComponent(fileName)}}`;
                  const input = document.getElementById("vl_copy_link");
                  const msg = document.getElementById("vl_copy_msg");
                  input.value = link;
                  async function copyText(text) {{
                    try {{
                      await navigator.clipboard.writeText(text);
                      return true;
                    }} catch (e) {{
                      try {{
                        const ta = document.createElement("textarea");
                        ta.value = text;
                        ta.style.position = "fixed";
                        ta.style.left = "-9999px";
                        document.body.appendChild(ta);
                        ta.focus();
                        ta.select();
                        const ok = document.execCommand("copy");
                        document.body.removeChild(ta);
                        return ok;
                      }} catch (e2) {{
                        return false;
                      }}
                    }}
                  }}
                  document.getElementById("vl_copy_btn").addEventListener("click", async () => {{
                    const ok = await copyText(link);
                    msg.textContent = ok ? "已复制" : "复制失败，请手动复制";
                  }});
                </script>
                """,
                height=90,
            )
            if st.button(t("Delete and Reselect"), key="delete_video_button"):
                os.remove(video_file)
                if os.path.exists(OUTPUT_DIR):
                    shutil.rmtree(OUTPUT_DIR)
                sleep(1)
                st.rerun()
            return True
        except Exception:
            col1, col2 = st.columns([3, 1])
            with col1:
                url = st.text_input(t("Enter YouTube link:"))
            with col2:
                res_dict = {
                    "360p": "360",
                    "1080p": "1080",
                    "Best": "best"
                }
                target_res = load_key("ytb_resolution")
                res_options = list(res_dict.keys())
                default_idx = list(res_dict.values()).index(target_res) if target_res in res_dict.values() else 0
                res_display = st.selectbox(t("Resolution"), options=res_options, index=default_idx)
                res = res_dict[res_display]

            download_subtitles = st.checkbox("同时下载 YouTube 字幕", value=False)
            subtitles_source = "auto"
            subtitles_langs = None
            subtitles_format = "srt"
            if download_subtitles:
                source_display = st.selectbox(
                    "字幕来源",
                    options=["自动字幕（YouTube 生成）", "上传字幕（视频自带）", "两者都下载"],
                    index=0,
                )
                source_map = {
                    "自动字幕（YouTube 生成）": "auto",
                    "上传字幕（视频自带）": "manual",
                    "两者都下载": "both",
                }
                subtitles_source = source_map.get(source_display, "auto")

                fmt_display = st.selectbox("字幕格式", options=["SRT", "VTT", "JSON3"], index=0)
                subtitles_format = fmt_display.lower()

                langs_text = st.text_input("字幕语言（逗号或空格分隔，可留空=默认）", value="")
                langs = [x.strip() for x in re.split(r"[,\s]+", langs_text) if x.strip()]
                subtitles_langs = langs or None

            if st.button(t("Download Video"), key="download_button", width="stretch"):
                if url:
                    with st.spinner("Downloading video..."):
                        download_video_ytdlp(
                            url,
                            resolution=res,
                            download_subtitles=download_subtitles,
                            subtitles_source=subtitles_source,
                            subtitles_langs=subtitles_langs,
                            subtitles_format=subtitles_format,
                        )
                    st.rerun()

            uploaded_file = st.file_uploader(t("Or upload video"), type=load_key("allowed_video_formats") + load_key("allowed_audio_formats"))
            if uploaded_file:
                if os.path.exists(OUTPUT_DIR):
                    shutil.rmtree(OUTPUT_DIR)
                # Save the uploaded file to the static/output directory
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                
                raw_name = uploaded_file.name.replace(' ', '_')
                name, ext = os.path.splitext(raw_name)
                clean_name = re.sub(r'[^\w\-_\.]', '', name) + ext.lower()
                    
                with open(os.path.join(OUTPUT_DIR, clean_name), "wb") as f:
                    f.write(uploaded_file.getbuffer())

                if ext.lower() in load_key("allowed_audio_formats"):
                    convert_audio_to_video(os.path.join(OUTPUT_DIR, clean_name))
                st.rerun()
            else:
                return False

def convert_audio_to_video(audio_file: str) -> str:
    output_video = os.path.join(OUTPUT_DIR, 'black_screen.mp4')
    if not os.path.exists(output_video):
        print(f"🎵➡️🎬 Converting audio to video with FFmpeg ......")
        ffmpeg_cmd = ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=640x360', '-i', audio_file, '-shortest', '-c:v', 'libx264', '-c:a', 'aac', '-pix_fmt', 'yuv420p', output_video]
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True, encoding='utf-8')
        print(f"🎵➡️🎬 Converted <{audio_file}> to <{output_video}> with FFmpeg\n")
        # delete audio file
        os.remove(audio_file)
    return output_video
