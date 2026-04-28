"""
FFmpeg Video + Audio Merger
Combines generated video with TTS audio
Handles duration matching, subtitles, and format conversion
"""
import subprocess
import os

def merge_video_audio(video_path: str, audio_path: str, output_path: str,
                      video_duration: float = None) -> str:
    """
    Merge video and audio. 
    - If audio is longer than video: loops the video to match audio length
    - If video is longer than audio: trims video to audio length
    """
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    
    print(f"[FFMPEG] Merging video + audio...")
    
    if video_duration:
        # Loop video to match audio duration
        cmd = [
            'ffmpeg', '-y',
            '-stream_loop', '-1',    # Loop video infinitely
            '-i', video_path,
            '-i', audio_path,
            '-t', str(video_duration),  # Cut to audio duration
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-pix_fmt', 'yuv420p',   # Required for Instagram/YouTube
            '-movflags', '+faststart', # Optimized for streaming
            output_path
        ]
    else:
        # Simple merge, shortest stream wins
        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', audio_path,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            '-shortest',   # Use shortest stream's length
            output_path
        ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"[FFMPEG ERROR] {result.stderr}")
        raise RuntimeError("FFmpeg merge failed")
    
    print(f"[FFMPEG] Final video saved: {output_path}")
    return output_path


def convert_for_instagram(input_path: str, output_path: str,
                           format='reel') -> str:
    """
    Convert video to Instagram-optimized format.
    format: 'reel' (9:16, vertical) or 'feed' (1:1, square)
    """
    if format == 'reel':
        width, height = 1080, 1920
    else:
        width, height = 1080, 1080
    
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,'
               f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black',
        '-c:v', 'libx264',
        '-crf', '23',         # Quality (lower = better, 18-28 is good range)
        '-preset', 'slow',    # Encoding speed vs compression
        '-c:a', 'aac',
        '-b:a', '192k',
        '-r', '30',           # 30fps for Instagram
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg conversion failed: {result.stderr}")
    
    print(f"[FFMPEG] Instagram-ready video: {output_path}")
    return output_path


def convert_for_youtube(input_path: str, output_path: str) -> str:
    """
    Convert to YouTube-optimized format (1080p, high quality).
    """
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,'
               'pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black',
        '-c:v', 'libx264',
        '-crf', '18',
        '-preset', 'slow',
        '-c:a', 'aac',
        '-b:a', '320k',
        '-r', '30',
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg conversion failed: {result.stderr}")
    
    print(f"[FFMPEG] YouTube-ready video: {output_path}")
    return output_path