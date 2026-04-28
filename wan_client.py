"""
ComfyUI / Wan2.1 API Client
Submits video generation jobs and waits for completion
"""
import json
import time
import uuid
import urllib.request
import urllib.parse
import websocket  # pip install websocket-client
import os
from pathlib import Path

COMFYUI_URL = "http://localhost:8188"
COMFYUI_WS  = "ws://localhost:8188/ws"

class WanVideoClient:
    def __init__(self, workflow_path: str):
        with open(workflow_path, 'r') as f:
            self.base_workflow = json.load(f)
        self.client_id = str(uuid.uuid4())
        print(f"[VIDEO] WanVideoClient initialized (client_id: {self.client_id[:8]}...)")

    def _find_node_by_title(self, title: str):
        """Find a node ID in the workflow by its _meta.title field."""
        for node_id, node in self.base_workflow.items():
            if node.get('_meta', {}).get('title', '') == title:
                return node_id
        return None

    def generate(self, prompt: str, output_dir: str,
                 width=832, height=480, num_frames=81,
                 steps=20, seed=None) -> str:
        """
        Submit a video generation job.
        
        Args:
            prompt: Text description of the video
            output_dir: Where to save the generated video
            width/height: Video dimensions (must be divisible by 16)
            num_frames: Number of frames (81 = ~5 sec at 16fps; max ~121 for 1.3B)
            steps: Inference steps (more = better quality, slower)
            seed: Random seed (None = random)
        
        Returns:
            Path to generated video file
        """
        import copy
        import random
        
        workflow = copy.deepcopy(self.base_workflow)
        
        # Set the prompt — find the CLIPTextEncode node
        # Node IDs vary by workflow; check your wan_workflow_api.json
        # Common node IDs for Wan2.1 workflows:
        for node_id, node in workflow.items():
            class_type = node.get('class_type', '')
            
            if class_type == 'CLIPTextEncode':
                workflow[node_id]['inputs']['text'] = prompt
                print(f"[VIDEO] Set prompt on node {node_id}")
            
            elif class_type in ('WanVideoSampler', 'KSampler'):
                if seed is None:
                    seed = random.randint(0, 2**32 - 1)
                workflow[node_id]['inputs']['seed'] = seed
                workflow[node_id]['inputs']['steps'] = steps
            
            elif class_type == 'EmptyHuanyuanLatentVideo':
                workflow[node_id]['inputs']['width'] = width
                workflow[node_id]['inputs']['height'] = height
                workflow[node_id]['inputs']['length'] = num_frames

        # Submit job
        prompt_id = self._queue_prompt(workflow)
        print(f"[VIDEO] Job queued: {prompt_id}")
        
        # Wait for completion via WebSocket
        output_filename = self._wait_for_completion(prompt_id)
        
        if not output_filename:
            raise RuntimeError("Video generation failed or timed out.")
        
        # Copy output to our directory
        comfy_output = f"ComfyUI/output/{output_filename}"
        
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        dest = os.path.join(output_dir, output_filename)
        
        import shutil
        shutil.copy2(comfy_output, dest)
        
        print(f"[VIDEO] Video saved: {dest}")
        return dest

    def _queue_prompt(self, workflow: dict) -> str:
        payload = json.dumps({
            "prompt": workflow,
            "client_id": self.client_id
        }).encode('utf-8')
        
        req = urllib.request.Request(
            f"{COMFYUI_URL}/prompt",
            data=payload,
            headers={'Content-Type': 'application/json'}
        )
        response = urllib.request.urlopen(req)
        result = json.loads(response.read())
        return result['prompt_id']

    def _wait_for_completion(self, prompt_id: str, timeout=600) -> str:
        """Wait for ComfyUI to finish generating via WebSocket."""
        ws = websocket.WebSocket()
        ws.connect(f"{COMFYUI_WS}?clientId={self.client_id}")
        
        start_time = time.time()
        output_file = None
        
        print("[VIDEO] Waiting for generation... (this takes 2-10 minutes)")
        
        try:
            while time.time() - start_time < timeout:
                message = ws.recv()
                if isinstance(message, str):
                    data = json.loads(message)
                    msg_type = data.get('type', '')
                    
                    if msg_type == 'progress':
                        step = data['data']['value']
                        total = data['data']['max']
                        pct = int(step / total * 100)
                        print(f"\r[VIDEO] Progress: {step}/{total} ({pct}%)", end='', flush=True)
                    
                    elif msg_type == 'executed':
                        if data['data']['prompt_id'] == prompt_id:
                            outputs = data['data'].get('output', {})
                            for node_output in outputs.values():
                                if 'gifs' in node_output:
                                    output_file = node_output['gifs'][0]['filename']
                                elif 'videos' in node_output:
                                    output_file = node_output['videos'][0]['filename']
                    
                    elif msg_type == 'execution_error':
                        print(f"\n[VIDEO ERROR] {data['data']}")
                        break
                        
        finally:
            ws.close()
        
        print()  # newline after progress
        return output_file