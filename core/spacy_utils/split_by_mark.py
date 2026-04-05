import os
import pandas as pd
import warnings
from core.spacy_utils.load_nlp_model import init_nlp, SPLIT_BY_MARK_FILE
from core.utils.config_utils import load_key, get_joiner
from rich import print as rprint

warnings.filterwarnings("ignore", category=FutureWarning)

def split_by_mark(nlp):
    whisper_language = load_key("whisper.language")
    language = load_key("whisper.detected_language") if whisper_language == 'auto' else whisper_language # consider force english case
    joiner = get_joiner(language)
    rprint(f"[blue]🔍 Using {language} language joiner: '{joiner}'[/blue]")
    chunks = pd.read_excel("static/output/log/cleaned_chunks.xlsx")
    chunks.text = chunks.text.apply(lambda x: x.strip('"').strip(""))
    
    # join with joiner but group by speaker_id first
    sentences_by_mark = []
    current_sentence = []

    # Group by contiguous speaker_id
    groups = []
    current_group = []
    current_speaker = None

    for _, row in chunks.iterrows():
        spk = row.get('speaker_id', None)
        if pd.isna(spk):
            spk = None
        elif isinstance(spk, (int, float)) and not isinstance(spk, bool):
            try:
                spk = int(spk)
            except Exception:
                spk = str(spk)
        if spk != current_speaker:
            if current_group:
                groups.append((current_speaker, current_group))
            current_group = [row['text']]
            current_speaker = spk
        else:
            current_group.append(row['text'])
    if current_group:
        groups.append((current_speaker, current_group))

    for spk, texts in groups:
        input_text = joiner.join(texts)
        doc = nlp(input_text)
        assert doc.has_annotation("SENT_START")

        # iterate all sentences in this speaker's group
        for sent in doc.sents:
            text = sent.text.strip()
            
            # check if the current sentence ends with - or ...
            if current_sentence and (
                text.startswith('-') or 
                text.startswith('...') or
                current_sentence[-1].endswith('-') or
                current_sentence[-1].endswith('...')
            ):
                current_sentence.append(text)
            else:
                if current_sentence:
                    sentences_by_mark.append(' '.join(current_sentence))
                    current_sentence = []
                current_sentence.append(text)
        
        # At the end of each speaker group, force a sentence break
        if current_sentence:
            sentences_by_mark.append(' '.join(current_sentence))
            current_sentence = []

    with open(SPLIT_BY_MARK_FILE, "w", encoding="utf-8") as output_file:
        for i, sentence in enumerate(sentences_by_mark):
            if i > 0 and sentence.strip() in [',', '.', '，', '。', '？', '！']:
                # ! If the current line contains only punctuation, merge it with the previous line, this happens in Chinese, Japanese, etc.
                output_file.seek(output_file.tell() - 1, os.SEEK_SET)  # Move to the end of the previous line
                output_file.write(sentence)  # Add the punctuation
            else:
                output_file.write(sentence + "\n")
    
    rprint(f"[green]💾 Sentences split by punctuation marks saved to →  `{SPLIT_BY_MARK_FILE}`[/green]")

if __name__ == "__main__":
    nlp = init_nlp()
    split_by_mark(nlp)
