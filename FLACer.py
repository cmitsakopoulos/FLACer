import io
import zipfile
from abc import ABC, abstractmethod
import streamlit as st
from pydub import AudioSegment
import mutagen
import mutagen.flac
import mutagen.mp3
import mutagen.mp4
from mutagen.id3 import ID3, APIC, TPE1, TALB, TIT2, TRCK, TDRC, TCON

class AudioConverter(ABC):
    @abstractmethod
    def process(self, file_data, bitrate, conversion_type, logger, filename):
        pass

class MP3_LAME(AudioConverter):
    def process(self, file_data, bitrate, conversion_type, logger, filename):
        logger.append(f"INFO: Starting MP3 conversion for '{filename}'.")
        
        file_data.seek(0)
        flac_meta = mutagen.flac.FLAC(file_data)
        logger.append("INFO: Successfully extracted source metadata.")

        file_data.seek(0)
        audio = AudioSegment.from_file(file_data, format="flac")
        logger.append(f"INFO: Loaded audio data. Duration: {len(audio) / 1000:.2f}s.")
        
        parameters = ['-codec:a', 'libmp3lame', '-id3v2_version', '3']
        if conversion_type == 'vbr':
            parameters.extend(['-q:a', '0'])
            logger.append("INFO: Applying VBR encoding (audio only).")
        else:
            parameters.extend(['-b:a', f'{bitrate}k'])
            logger.append(f"INFO: Applying {conversion_type.upper()} encoding (audio only).")
            
        output_buffer = io.BytesIO()
        audio.export(output_buffer, format="mp3", parameters=parameters)
        logger.append("INFO: Audio conversion complete. Applying metadata.")

        output_buffer.seek(0)
        mp3_meta = mutagen.mp3.MP3(output_buffer, ID3=ID3)
        
        tag_map = {
            'artist': TPE1, 'album': TALB, 'title': TIT2, 
            'tracknumber': TRCK, 'date': TDRC, 'genre': TCON
        }
        for key, value in flac_meta.items():
            frame_class = tag_map.get(key.lower())
            if frame_class:
                mp3_meta.tags.add(frame_class(encoding=3, text=value[0]))

        if flac_meta.pictures:
            pic = flac_meta.pictures[0]
            mp3_meta.tags.add(APIC(encoding=3, mime=pic.mime, type=pic.type, desc=pic.desc, data=pic.data))
        
        mp3_meta.save(output_buffer)
        logger.append("INFO: Metadata successfully applied.")
        
        logger.append(f"SUCCESS: Finished MP3 conversion for '{filename}'.")
        return output_buffer

class AAC_better(AudioConverter):
    def process(self, file_data, bitrate, conversion_type, logger, filename):
        logger.append(f"INFO: Starting M4A (AAC) conversion for '{filename}'.")

        file_data.seek(0)
        flac_meta = mutagen.flac.FLAC(file_data)
        logger.append("INFO: Successfully extracted source metadata.")

        file_data.seek(0)
        audio = AudioSegment.from_file(file_data, format="flac")
        logger.append(f"INFO: Loaded audio data. Duration: {len(audio) / 1000:.2f}s.")
        
        parameters = ['-c:a', 'aac']
        if conversion_type == 'vbr':
            parameters.extend(['-q:a', '2'])
            logger.append("INFO: Applying VBR encoding (audio only).")
        else:
            parameters.extend(['-b:a', f'{bitrate}k'])
            logger.append(f"INFO: Applying {conversion_type.upper()} encoding (audio only).")

        output_buffer = io.BytesIO()
        audio.export(output_buffer, format="mp4", parameters=parameters)
        logger.append("INFO: Audio conversion complete. Applying metadata.")

        output_buffer.seek(0)
        mp4_meta = mutagen.mp4.MP4(output_buffer)
        
        tag_map = {
            'artist': '\xa9ART', 'album': '\xa9alb', 'title': '\xa9nam',
            'tracknumber': 'trkn', 'date': '\xa9day', 'genre': '\xa9gen'
        }
        for key, value in flac_meta.items():
            tag_key = tag_map.get(key.lower())
            if not tag_key:
                continue

            if tag_key == 'trkn':
                try:
                    track_info = value[0].split('/')
                    track_num = int(track_info[0])
                    total_tracks = int(track_info[1]) if len(track_info) > 1 else 0
                    mp4_meta[tag_key] = [(track_num, total_tracks)]
                except (ValueError, IndexError):
                    logger.append(f"WARNING: Could not parse track number '{value[0]}'. Skipping.")
            else:
                mp4_meta[tag_key] = value[0]

        if flac_meta.pictures:
            pic = flac_meta.pictures[0]
            image_format = mutagen.mp4.MP4Cover.FORMAT_JPEG if pic.mime == 'image/jpeg' else mutagen.mp4.MP4Cover.FORMAT_PNG
            mp4_meta['covr'] = [mutagen.mp4.MP4Cover(pic.data, imageformat=image_format)]
        
        mp4_meta.save(output_buffer)
        logger.append("INFO: Metadata successfully applied.")
        
        logger.append(f"SUCCESS: Finished M4A conversion for '{filename}'.")
        return output_buffer

class Fucktory:
    @staticmethod
    def get_converter(format):
        if format == 'mp3':
            return MP3_LAME()
        elif format == 'm4a':
            return AAC_better()
        raise ValueError("Unknown format specified")

def main():
    st.set_page_config(layout="wide", page_title="FLACer")

    if 'format' not in st.session_state:
        st.session_state.format = None
    if 'type' not in st.session_state:
        st.session_state.type = None
    if 'logs' not in st.session_state:
        st.session_state.logs = []

    def select_option(format, type):
        st.session_state.format = format
        st.session_state.type = type

    st.title("FLACer")
    st.markdown("<p style='color: #9ca3af;'>Convert your lossless FLAC files to high-bitrate MP3 or M4A.</p>", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["Converter", "Logs"])

    with tab1:
        configure_converter_ui(select_option)

    with tab2:
        display_logs()

    update_button_styles_js()

def configure_converter_ui(select_option_callback):
    st.markdown("""
    <style>
        .stButton>button {
            width: 100%;
            border: 2px solid #4b5563;
            transition: all 0.2s ease-in-out;
        }
        .stButton>button:hover {
            border-color: #60a5fa;
            color: #60a5fa;
        }
        .selected-button {
            background-color: #3b82f6 !important;
            color: white !important;
            border-color: #3b82f6 !important;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("### 1. Upload FLAC")
    uploaded_files = st.file_uploader(
        "Select one or more FLAC files",
        type=["flac"],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )

    st.markdown("### 2. Conversion Options")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("M4A (AAC)")
        st.button("Constant Bitrate (CBR)", on_click=select_option_callback, args=('m4a', 'cbr'), key='cbr_m4a')
        st.button("Variable Bitrate (VBR)", on_click=select_option_callback, args=('m4a', 'vbr'), key='vbr_m4a')
        st.button("Average Bitrate (ABR)", on_click=select_option_callback, args=('m4a', 'abr'), key='abr_m4a')

    with col2:
        st.subheader("MP3")
        st.button("Constant Bitrate (CBR)", on_click=select_option_callback, args=('mp3', 'cbr'), key='cbr_mp3')
        st.button("Variable Bitrate (VBR)", on_click=select_option_callback, args=('mp3', 'vbr'), key='vbr_mp3')
        st.button("Average Bitrate (ABR)", on_click=select_option_callback, args=('mp3', 'abr'), key='abr_mp3')

    st.markdown("### 3. Convert files")
    if st.session_state.format and st.session_state.type:
        button_text = f"Convert to {st.session_state.format.upper()} ({st.session_state.type.upper()}) at 320kbps"
        if st.button(button_text, type="primary", use_container_width=True):
            if uploaded_files:
                process_files(uploaded_files)
            else:
                st.warning("Can't make something out of nothing.")
    else:
        st.button("Select an Option to Continue", use_container_width=True, disabled=True)

def display_logs():
    st.subheader("Conversion Logs")
    if not st.session_state.logs:
        st.info("meow")
    else:
        log_container = st.container()
        log_text = "\n".join(st.session_state.logs)
        log_container.code(log_text, language='log')

def process_files(files):
    st.session_state.logs = []
    logger = st.session_state.logs
    
    selected_format = st.session_state.format
    conversion_type = st.session_state.type
    
    logger.append(f"BATCH START: Initializing conversion for {len(files)} file(s).")
    logger.append(f"BATCH INFO: Target format: {selected_format.upper()}, Type: {conversion_type.upper()}.")
    
    try:
        converter = Fucktory.get_converter(selected_format)
        
        with st.spinner(f"Converting {len(files)} file(s)..."):
            if len(files) == 1:
                file = files[0]
                output_buffer = converter.process(file, 320, conversion_type, logger, file.name)
                st.success(f"Conversion of '{file.name}' successful!")
                st.download_button(
                    label=f"Download {selected_format.upper()}",
                    data=output_buffer,
                    file_name=f"{file.name.rsplit('.', 1)[0]}.{selected_format}",
                    mime=f"audio/{'mpeg' if selected_format == 'mp3' else 'mp4'}",
                    use_container_width=True
                )
            else:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for i, file in enumerate(files):
                        logger.append("-" * 30)
                        logger.append(f"INFO: Processing file {i+1} of {len(files)}: '{file.name}'")
                        output_buffer = converter.process(file, 320, conversion_type, logger, file.name)
                        new_filename = f"{file.name.rsplit('.', 1)[0]}.{selected_format}"
                        zip_file.writestr(new_filename, output_buffer.getvalue())
                
                logger.append("-" * 30)
                logger.append("BATCH SUCCESS: All files converted and zipped successfully!")
                st.success("All files converted and zipped successfully!")
                st.download_button(
                    label="Download All as ZIP",
                    data=zip_buffer.getvalue(),
                    file_name="converted_audio.zip",
                    mime="application/zip",
                    use_container_width=True
                )

    except Exception as e:
        logger.append(f"ERROR: An unexpected error occurred: {e}")
        st.error(f"An error occurred during conversion: {e}")

def update_button_styles_js():
    js = f"""
    <script>
        const buttons = window.parent.document.querySelectorAll('.stButton button');
        buttons.forEach(btn => {{
            btn.classList.remove('selected-button');
        }});

        const selectedFormat = "{st.session_state.get('format', '')}";
        const selectedType = "{st.session_state.get('type', '')}";

        if (selectedFormat && selectedType) {{
            const key = `${{selectedType}}_${{selectedFormat}}`;
            const frame = window.parent.document.querySelector('[data-testid="stAppViewContainer"]');
            const selectedBtn = frame.querySelector(`button[data-testid="st.button(key='${{key}}')"]`);
            if(selectedBtn) {{
                selectedBtn.classList.add('selected-button');
            }}
        }}
    </script>
    """
    st.components.v1.html(js, height=0)

if __name__ == "__main__":
    main()