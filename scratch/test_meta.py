import re

def generate_podcast_title_desc(source_title, candidate_text, is_short=True):
    # 1. Parse speaker / topic
    speaker = ''
    topic = source_title
    if ':' in source_title:
        parts = source_title.split(':', 1)
        speaker = parts[0].strip()
        topic = parts[1].strip()
    elif ' - ' in source_title:
        parts = source_title.split(' - ', 1)
        speaker = parts[0].strip()
        topic = parts[1].strip()
        
    # Clean topic
    topic = re.sub(r'\[.*?\]|\(.*?\)|#\d+', '', topic).strip()
    
    # 2. Extract punchline sentence from transcript excerpt
    sentences = re.split(r'[.!?]+', candidate_text)
    punchline = next((s.strip() for s in sentences if len(s.strip().split()) >= 4 and len(s.strip().split()) <= 12), '')
    
    tag = '#Shorts' if is_short else '#Podcast'
    emoji = '🤯' if any(w in candidate_text.lower() for w in ['ai', 'future', 'mind', 'crazy', 'insane', 'threat', 'secret']) else '🧠'
    
    if speaker and topic:
        raw_title = f"{speaker}: {topic}"
    elif speaker and punchline:
        raw_title = f"{speaker}: \"{punchline}\""
    else:
        raw_title = source_title
        
    max_body_len = 100 - len(tag) - len(emoji) - 3
    if len(raw_title) > max_body_len:
        raw_title = raw_title[:max_body_len - 3].rsplit(' ', 1)[0] + '...'
        
    final_title = f"{raw_title} {emoji} {tag}".strip()
    if len(final_title) > 100:
        final_title = final_title[:95] + '...'
        
    snippet = ' '.join(candidate_text.split()[:50])
    desc = (
        f"🔥 {final_title}\n\n"
        f"💡 Key Insight:\n\"{snippet}...\"\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎙️ Source Episode: {source_title}\n\n"
        f"👉 Subscribe for daily mind-expanding podcast clips, science breakdowns, and deep life wisdom!\n\n"
        f"#shorts #podcast #mindset #motivation #wisdom #psychology #science #viral #trending #reels"
    )
    return final_title, desc

if __name__ == "__main__":
    t1, d1 = generate_podcast_title_desc(
        "Professor Brian Greene: The Threat of AI, Consciousness and Reality", 
        "I think it is right that we worry about the future of artificial intelligence because what it can do is beyond what we imagined."
    )
    print("TITLE 1 (len=" + str(len(t1)) + "):", t1)
    print("\nDESC 1:\n", d1)
