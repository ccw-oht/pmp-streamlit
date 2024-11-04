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

def parse_transcript(file_path):
    with open(file_path, "r") as f:
        raw_transcript = f.read()
        print(raw_transcript)
        
    def normalize_timestamp(timestamp: str) -> str:
        """Normalize timestamp to HH:MM:SS format."""
        parts = timestamp.split(':')
        if len(parts) == 2:  # MM:SS format
            return f'00:{parts[0]:0>2}:{parts[1]:0>2}'  # Add leading zeros for HH
        elif len(parts) == 3:  # HH:MM:SS format
            return f'{parts[0]:0>2}:{parts[1]:0>2}:{parts[2]:0>2}'  # Ensure all parts have leading zeros
        return timestamp  # Return as is if it doesn't match expected formats

    def extract_transcript_entries(transcript):
        entries = []
        lines = transcript.split('\n')
        for i in range(len(lines)):
            #print(f"Processing line: {line}")  # Debugging: Print each line being processed

            if re.match(r'^\d+;.*$', lines[i]):
                timestamp = lines[i].split(' - ')[0]
                speaker = next((lines[j] for j in range(i+1, len(lines)) if lines[j].strip() and not re.match(r'^\d+;.*$', lines[j])), None)
                text = next((lines[j] for j in range(i+2, len(lines)) if lines[j].strip() and not re.match(r'^\d+;.*$', lines[j])), None)
                entry = {'timestamp': timestamp, 'speaker': speaker, 'text': text}
                entries.append(entry)
            else:
                for line in lines:
                    #print(f"Processing line (YouTube): {line}")  # Debugging: Print each line being processed
                    # Assuming the timestamp is at the start of the line and is in the format "MM:SS" or "HH:MM:SS"
                    timestamp = lines[i].strip()
                    match = re.match(r'(\d{1,2}:\d{2}(:\d{2})?)\s*(.*)', line)
                    if match:
                        timestamp = normalize_timestamp(match.group(1))  # Normalize the timestamp
                        text = match.group(3).strip()  # Get the text after the timestamp
                    if text:  # Only add non-empty entries
                        entry = {'timestamp': timestamp, 'text': text}
                        entries.append(entry)
                
        return entries

    transcript_entries = extract_transcript_entries(raw_transcript)

    # New code to combine contiguous entries by the same speaker
    if transcript_entries:
        combined_entries = []
        for entry in transcript_entries:
            # Check if 'speaker' key exists before accessing it
            if 'speaker' in entry:
                if combined_entries and combined_entries[-1].get('speaker') == entry['speaker']:
                    combined_entries[-1]['text'] += ' ' + entry['text']  # Combine text
                else:
                    combined_entries.append(entry)  # Add new entry
            else:
                combined_entries.append(entry)  # Add entry if 'speaker' key does not exist
        # Adjust timestamps
        for entry in combined_entries:
            entry['timestamp'] = entry['timestamp'].replace(';', ':')[:-3]
            
        transcript_path = os.path.join(output_dir, f"{video_id}_parsed_transcript.json")
        # Save to JSON
        with open(transcript_path, 'w') as f:
            json.dump(combined_entries, f)
    
if __name__ == "__main__":

    base_url = st.text_input(
        "YouTube URL",
        value="",
        placeholder="https://www.youtube.com/watch?v=y7alkZndrFQ")

    if base_url:
        video_id = extract_video_id(base_url)
        output_dir = os.path.join(".", f"yt_video_{video_id}")
        os.makedirs(output_dir, exist_ok=True)
        #st.write(output_dir)
        #base_url)
        #yt_embed = st.video_embed(video_id)
        with elements("media_player"):
            from streamlit_elements import media
            media.Player(url=base_url, controls=True)
        
    transcript = st.text_area(
        "Raw Transcript",
        value=""
    )
    if transcript:
        with open(f"{output_dir}/{video_id}_raw_transcript.txt", 'w') as f:
            f.write(transcript)
        #st.write(transcript)
        
        parse_transcript(f"{output_dir}/{video_id}_raw_transcript.txt")
        
        
        #st.write(f"{output_dir}/{video_id}_parsed_transcript.json")
        st.header("Parsed Transcript") 
        with open(f"{output_dir}/{video_id}_parsed_transcript.json", "r") as f:
            data = json.load(f)
            df = pd.json_normalize(data=data)
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
                }
            )