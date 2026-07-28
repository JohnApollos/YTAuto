import ffmpeg
import os

class FFmpegCompositor:
    def __init__(self, input_video_path: str, output_path: str):
        self.input_video_path = input_video_path
        self.output_path = output_path
        
    def render_vertical_short(self, start_time_s: int, end_time_s: int, subtitle_path: str = None):
        """
        Extracts a segment from the input video, scales and blurs it for a 9:16 background,
        overlays the original 16:9 video in the center, and burns in subtitles.
        """
        duration = end_time_s - start_time_s
        
        # Open input file and trim to the desired segment
        stream = ffmpeg.input(self.input_video_path, ss=start_time_s, t=duration)
        video = stream.video
        audio = stream.audio
        
        # Vertical target dimensions (1080x1920)
        target_w = 1080
        target_h = 1920
        
        # 1. Background: Crop/scale to 9:16 and apply heavy blur
        background = (
            video
            .filter('scale', target_w, target_h, force_original_aspect_ratio='increase')
            .filter('crop', target_w, target_h)
            .filter('boxblur', 20)
            .filter('setsar', 1)
        )
        
        # 2. Foreground: Scale original video to fit width (1080x608 for a 16:9 video)
        foreground = (
            video
            .filter('scale', target_w, -1)
            .filter('setsar', 1)
        )
        
        # 3. Composite foreground over background in the center
        composed = ffmpeg.overlay(background, foreground, x=0, y='(H-h)/2')
        
        # 4. Burn in subtitles if provided
        if subtitle_path and os.path.exists(subtitle_path):
            # Escape path for ffmpeg filter
            safe_sub_path = subtitle_path.replace('\\', '/')
            composed = composed.filter('subtitles', safe_sub_path, force_style='FontSize=24,PrimaryColour=&H00FFFFFF,Alignment=2')
            
        print(f"[FFmpegCompositor] Constructing filtergraph for {self.output_path}...")
        
        try:
            # Output node combining video and original audio
            out = ffmpeg.output(
                composed, audio, self.output_path,
                vcodec='libx264',
                acodec='aac',
                video_bitrate='4M',
                audio_bitrate='192k',
                preset='fast'
            )
            
            # Execute FFmpeg (quiet output unless error)
            # In a real environment, we may want to capture stdout for progress bars
            ffmpeg.run(out, overwrite_output=True, capture_stdout=True, capture_stderr=True)
            print(f"[FFmpegCompositor] Successfully rendered {self.output_path}")
            
        except ffmpeg.Error as e:
            print("[FFmpegCompositor] FFmpeg Error!")
            if e.stderr:
                print(e.stderr.decode('utf8'))
            raise Exception("FFmpeg rendering failed") from e
