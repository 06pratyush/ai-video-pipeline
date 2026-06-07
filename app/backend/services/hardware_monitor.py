"""Hardware detection and monitoring."""
import subprocess
import platform
from dataclasses import dataclass


@dataclass
class HardwareInfo:
    gpu_name: str = "Unknown"
    vram_total_mb: int = 0
    vram_free_mb: int = 0
    vram_tier: str = "unknown"  # low / mid / high / ultra
    cpu_cores: int = 0
    ram_total_gb: float = 0.0
    platform: str = ""

    @property
    def vram_total_gb(self) -> float:
        return self.vram_total_mb / 1024


def detect_hardware() -> HardwareInfo:
    info = HardwareInfo(platform=platform.system())
    try:
        import psutil
        info.cpu_cores = psutil.cpu_count(logical=False) or 0
        info.ram_total_gb = round(psutil.virtual_memory().total / (1024**3), 1)
    except ImportError:
        pass

    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            if len(parts) >= 3:
                info.gpu_name = parts[0]
                info.vram_total_mb = int(parts[1])
                info.vram_free_mb = int(parts[2])
                vram_gb = info.vram_total_mb / 1024
                if vram_gb >= 24:
                    info.vram_tier = "ultra"
                elif vram_gb >= 16:
                    info.vram_tier = "high"
                elif vram_gb >= 12:
                    info.vram_tier = "mid"
                else:
                    info.vram_tier = "low"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return info


def get_free_vram_mb() -> int:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
    except Exception:
        pass
    return 0
