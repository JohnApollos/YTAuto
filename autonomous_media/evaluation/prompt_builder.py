import json
from typing import List, Dict, Any
from autonomous_media.db.models import CandidateClip

SYSTEM_PROMPT = """You are an expert TikTok and YouTube Shorts producer. 
Your job is to evaluate short video clips from a podcast transcript and score them on their potential to go viral.

You will be provided with a JSON array of candidate clips. Each clip has an 'id' and 'transcript_text'.

Score each clip from 1 to 10 on the following criteria:
1. hook_score: How attention-grabbing is the first 3 seconds? Does it make the viewer stop scrolling?
2. virality_score: How likely is this to be shared or commented on? Is it controversial, highly educational, or deeply emotional?
3. coherence_score: Does the clip make sense on its own without the surrounding context?

Calculate the total_score as the sum of the three scores (max 30).
Provide a brief 1-2 sentence reasoning for your scores.

You MUST respond with a raw JSON array matching this exact schema for each clip:
[
  {
    "candidate_clip_id": "<the id provided>",
    "hook_score": <int 1-10>,
    "virality_score": <int 1-10>,
    "coherence_score": <int 1-10>,
    "total_score": <int 3-30>,
    "llm_reasoning": "<your reasoning>"
  }
]
"""

class BatchedEvaluationPrompt:
    def __init__(self, clips: List[CandidateClip]):
        self.clips = clips
        # We assume 1 token ~= 4 characters for a rough estimate
        self.estimated_tokens = sum(len(c.transcript_text) for c in clips) // 4
    
    def build_prompt_messages(self) -> List[Dict[str, str]]:
        # Format the clips into a JSON array for the user message
        clips_data = [
            {
                "id": str(c.id),
                "transcript_text": c.transcript_text
            }
            for c in self.clips
        ]
        
        user_content = json.dumps(clips_data, indent=2)
        
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Evaluate the following clips:\n{user_content}"}
        ]

def chunk_clips(clips: List[CandidateClip], max_tokens: int = 6000) -> List[List[CandidateClip]]:
    """Chunks a large list of clips into smaller batches to fit within the LLM context window."""
    batches = []
    current_batch = []
    current_tokens = 0
    
    for clip in clips:
        clip_tokens = len(clip.transcript_text) // 4
        if current_tokens + clip_tokens > max_tokens and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0
            
        current_batch.append(clip)
        current_tokens += clip_tokens
        
    if current_batch:
        batches.append(current_batch)
        
    return batches
