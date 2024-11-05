import streamlit as st
from streamlit_player import st_player
from streamlit_elements import elements
import json
import re
import os
import pandas as pd

def extract_video_id(url):
    """
    Extracts the video ID from a YouTube URL.
    """
    pattern = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    else:
        raise ValueError("Invalid YouTube URL")

def detect_transcript_format(transcript_text: str) -> str:
    """Detect the format of the transcript based on its content."""
    lines = transcript_text.strip().split('\n')
    
    # Check first few non-empty lines for format detection
    for line in lines[:10]:
        if not line.strip():
            continue
            
        # Adobe format with line numbers and speakers (format: "1| 00;01;21;11 - 00;01;51;00")
        if re.match(r'^\d+\|\s*\d{2};\d{2};\d{2};\d{2}\s*-\s*\d{2};\d{2};\d{2};\d{2}', line):
            return "adobe_numbered"
            
        # Adobe format with speakers (format: "00;01;21;11 - 00;01;51;00")
        if re.match(r'^\d{2};\d{2};\d{2};\d{2}\s*-\s*\d{2};\d{2};\d{2};\d{2}', line):
            return "adobe"
            
        # YouTube format (format: "1:15:16" or simple line number + text)
        if re.match(r'^\d+\|\s*$', line) or re.match(r'^\d{1,2}:\d{2}:\d{2}$', line):
            return "youtube"
    
    return "unknown"

def normalize_timestamp(timestamp: str) -> str:
    """Normalize timestamp to HH:MM:SS format."""
    # Handle empty or invalid timestamps
    if not timestamp:
        return "00:00:00"
    
    # Remove frame numbers if present (after last semicolon)
    if ';' in timestamp:
        parts = timestamp.split(';')[:3]  # Take only HH;MM;SS
        timestamp = ':'.join(parts)
    
    # Split into parts
    parts = timestamp.split(':')
    
    try:
        if len(parts) == 1:  # SS
            return f'00:00:{int(parts[0]):02d}'
        elif len(parts) == 2:  # MM:SS
            return f'00:{int(parts[0]):02d}:{int(parts[1]):02d}'
        elif len(parts) == 3:  # HH:MM:SS
            return f'{int(parts[0]):02d}:{int(parts[1]):02d}:{int(parts[2]):02d}'
    except ValueError:
        return "00:00:00"
    
    return timestamp

def extract_transcript_entries(transcript: str) -> list:
    """Extract transcript entries based on content format."""
    entries = []
    lines = transcript.strip().split('\n')
    current_entry = None
    
    # Try to detect if this is an Adobe format transcript
    is_adobe = any(';' in line for line in lines[:10])
    
    if is_adobe:
        # Adobe format parsing
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Match timestamp range pattern
            timestamp_match = re.match(r'(\d{2};\d{2};\d{2};\d{2})\s*-\s*\d{2};\d{2};\d{2};\d{2}', line)
            if timestamp_match:
                if current_entry and 'text' in current_entry:
                    entries.append(current_entry)
                current_entry = {'timestamp': normalize_timestamp(timestamp_match.group(1))}
            elif line.startswith('Speaker '):
                if current_entry:
                    current_entry['speaker'] = line.strip()
            elif current_entry:
                if 'text' not in current_entry:
                    current_entry['text'] = line
                else:
                    current_entry['text'] += ' ' + line
    else:
        # YouTube format parsing
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Match timestamp pattern (1:23 or 1:23:45)
            timestamp_match = re.match(r'^(\d+:?\d{2}(:\d{2})?)\s*$', line)
            if timestamp_match:
                if current_entry and 'text' in current_entry:
                    entries.append(current_entry)
                current_entry = {'timestamp': normalize_timestamp(timestamp_match.group(1)), 'text': ''}
            elif current_entry:
                text = line.strip()
                if text:
                    current_entry['text'] = text
    
    # Add the last entry if it exists
    if current_entry and 'text' in current_entry:
        entries.append(current_entry)
    
    return entries

def parse_transcript(file_path):
    """Parse transcript file and save as JSON."""
    with open(file_path, "r") as f:
        raw_transcript = f.read()
    
    transcript_entries = extract_transcript_entries(raw_transcript)
    
    # Save to JSON in the same directory as the transcript file
    transcript_path = "parsed_transcript.json"  # Use fixed path as in original code
    with open(transcript_path, 'w') as f:
        json.dump(transcript_entries, f, indent=4)
    
    return transcript_entries

if __name__ == "__main__":

    base_url = st.text_input(
        "YouTube URL",
        value="",
        placeholder="https://www.youtube.com/watch?v=y7alkZndrFQ")

    if base_url:
        video_id = extract_video_id(base_url)
        output_dir = os.path.join(".", f"yt_video_{video_id}")
        os.makedirs(output_dir, exist_ok=True)
        
        with elements("media_player"):
            from streamlit_elements import media
            media.Player(url=base_url, controls=True)
        
    transcript = st.text_area(
        "Raw Transcript",
        value=""
    )
    
    if transcript:
        # Save raw transcript
        transcript_file = f"{output_dir}/{video_id}_raw_transcript.txt"
        with open(transcript_file, 'w') as f:
            f.write(transcript)
        
        # Parse and get entries
        entries = parse_transcript(transcript_file)
        
        # Display parsed transcript
        st.header("Parsed Transcript")
        if entries:  # Only create dataframe if we have entries
            df = pd.json_normalize(entries)
            if not df.empty:  # Check if dataframe has data
                edited_df = st.data_editor(
                    df,
                    column_config={
                        "timestamp": st.column_config.TextColumn(
                            "Timestamp",
                            validate=r'(\d{2}:\d{2}:\d{2})'
                        ),
                        "text": st.column_config.TextColumn(
                            "Text",
                            help="Text from combined speakers.",
                            disabled=True,                    
                        ),
                        "speaker": st.column_config.TextColumn(
                            "Speaker",
                            help="Speaker name if available",
                            disabled=True,
                        ) if "speaker" in df.columns else None,
                    }
                )
        else:
            st.warning("No entries were parsed from the transcript.")