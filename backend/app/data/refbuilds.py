from typing import TypedDict

class Part(TypedDict):
    component: str
    brand: str
    model: str
    approx_price: int  # USD

class Build(TypedDict):
    label: str
    description: str
    total_approx: int
    parts: list[Part]

BUILDS: dict[str, Build] = {
    "entry_gaming_1080p": {
        "label": "Entry Gaming — 1080p",
        "description": "Solid 1080p performance for popular titles at high settings without breaking the bank.",
        "total_approx": 1000,
        "parts": [
            {"component": "CPU", "brand": "AMD", "model": "Ryzen 5 5600", "approx_price": 160},
            {"component": "GPU", "brand": "AMD", "model": "Radeon RX 7600", "approx_price": 300},
            {"component": "Motherboard", "brand": "MSI", "model": "B550M PRO-VDH WiFi", "approx_price": 100},
            {"component": "RAM", "brand": "G.Skill", "model": "Ripjaws V 16GB DDR4-3600", "approx_price": 160},
            {"component": "Storage", "brand": "Samsung", "model": "870 EVO 1TB SATA SSD", "approx_price": 180},
            {"component": "PSU", "brand": "Thermaltake", "model": "550 G6 80+ Gold", "approx_price": 70},
            {"component": "Case", "brand": "Fractal Design", "model": "Pop Air", "approx_price": 80},
        ],
    },
    "mid_gaming_1080p": {
        "label": "Mid-Range Gaming — 1080p",
        "description": "High-refresh 1080p gaming. Handles everything at ultra settings with frames to spare.",
        "total_approx": 1000,
        "parts": [
            {"component": "CPU", "brand": "AMD", "model": "Ryzen 5 7600X", "approx_price": 200},
            {"component": "GPU", "brand": "NVIDIA", "model": "RTX 4060 Ti", "approx_price": 380},
            {"component": "Motherboard", "brand": "ASUS", "model": "ROG Strix B650-A Gaming WiFi", "approx_price": 200},
            {"component": "RAM", "brand": "G.Skill", "model": "Flare X5 32GB DDR5-6000", "approx_price": 90},
            {"component": "Storage", "brand": "Samsung", "model": "990 Pro 1TB NVMe", "approx_price": 100},
            {"component": "PSU", "brand": "Seasonic", "model": "Focus GX-750 80+ Gold", "approx_price": 110},
            {"component": "Case", "brand": "Lian Li", "model": "Lancool 216", "approx_price": 100},
        ],
    },
    "mid_gaming_1440p": {
        "label": "Mid-Range Gaming — 1440p",
        "description": "The sweet spot. Smooth 1440p gaming on demanding titles with headroom for the future.",
        "total_approx": 1300,
        "parts": [
            {"component": "CPU", "brand": "AMD", "model": "Ryzen 7 7700X", "approx_price": 280},
            {"component": "GPU", "brand": "NVIDIA", "model": "RTX 4070 Super", "approx_price": 580},
            {"component": "Motherboard", "brand": "ASUS", "model": "ROG Strix B650-A Gaming WiFi", "approx_price": 200},
            {"component": "RAM", "brand": "G.Skill", "model": "Flare X5 32GB DDR5-6000", "approx_price": 90},
            {"component": "Storage", "brand": "Samsung", "model": "990 Pro 1TB NVMe", "approx_price": 100},
            {"component": "PSU", "brand": "Seasonic", "model": "Focus GX-850 80+ Gold", "approx_price": 130},
            {"component": "Case", "brand": "Fractal Design", "model": "North", "approx_price": 140},
        ],
    },
    "high_gaming_1440p": {
        "label": "High-End Gaming — 1440p / Light 4K",
        "description": "Max settings at 1440p, playable 4K on most titles. Built for demanding games and high refresh rates.",
        "total_approx": 1900,
        "parts": [
            {"component": "CPU", "brand": "AMD", "model": "Ryzen 9 7900X", "approx_price": 380},
            {"component": "GPU", "brand": "NVIDIA", "model": "RTX 4080 Super", "approx_price": 950},
            {"component": "Motherboard", "brand": "ASUS", "model": "ProArt X670E-Creator WiFi", "approx_price": 350},
            {"component": "RAM", "brand": "G.Skill", "model": "Trident Z5 32GB DDR5-6400", "approx_price": 110},
            {"component": "Storage", "brand": "Samsung", "model": "990 Pro 2TB NVMe", "approx_price": 160},
            {"component": "PSU", "brand": "Seasonic", "model": "Vertex GX-1000 80+ Gold", "approx_price": 180},
            {"component": "Case", "brand": "Lian Li", "model": "O11 Dynamic EVO", "approx_price": 150},
        ],
    },
    "creator_1080p_editing": {
        "label": "Content Creator — 1080p Video Editing",
        "description": "Fast exports and smooth timelines for 1080p content. Great for YouTube, Reels, and streaming.",
        "total_approx": 1200,
        "parts": [
            {"component": "CPU", "brand": "AMD", "model": "Ryzen 9 7900X", "approx_price": 380},
            {"component": "GPU", "brand": "NVIDIA", "model": "RTX 4060 Ti", "approx_price": 380},
            {"component": "Motherboard", "brand": "ASUS", "model": "ProArt B650-Creator WiFi", "approx_price": 220},
            {"component": "RAM", "brand": "G.Skill", "model": "Flare X5 64GB DDR5-6000", "approx_price": 160},
            {"component": "Storage", "brand": "Samsung", "model": "990 Pro 2TB NVMe", "approx_price": 160},
            {"component": "PSU", "brand": "Seasonic", "model": "Focus GX-750 80+ Gold", "approx_price": 110},
            {"component": "Case", "brand": "Fractal Design", "model": "Torrent", "approx_price": 180},
        ],
    },
    "local_llm": {
        "label": "Local LLM / AI Build",
        "description": "Maximize VRAM for running large local models. Handles 13B–70B quantized models with ease.",
        "total_approx": 2200,
        "parts": [
            {"component": "CPU", "brand": "AMD", "model": "Ryzen 9 7900X", "approx_price": 380},
            {"component": "GPU", "brand": "NVIDIA", "model": "RTX 4090", "approx_price": 1600},
            {"component": "Motherboard", "brand": "ASUS", "model": "ProArt X670E-Creator WiFi", "approx_price": 350},
            {"component": "RAM", "brand": "G.Skill", "model": "Trident Z5 64GB DDR5-6000", "approx_price": 200},
            {"component": "Storage", "brand": "Samsung", "model": "990 Pro 2TB NVMe", "approx_price": 160},
            {"component": "PSU", "brand": "Seasonic", "model": "Vertex GX-1000 80+ Gold", "approx_price": 180},
            {"component": "Case", "brand": "Lian Li", "model": "O11 Dynamic EVO", "approx_price": 150},
        ],
    },
    "budget_allrounder": {
        "label": "Budget All-Rounder",
        "description": "Web browsing, office work, light gaming, and media consumption. Efficient and reliable.",
        "total_approx": 450,
        "parts": [
            {"component": "CPU", "brand": "AMD", "model": "Ryzen 5 5500", "approx_price": 90},
            {"component": "GPU", "brand": "AMD", "model": "Radeon RX 6600", "approx_price": 200},
            {"component": "Motherboard", "brand": "MSI", "model": "B450M PRO-VDH MAX", "approx_price": 75},
            {"component": "RAM", "brand": "Corsair", "model": "Vengeance LPX 16GB DDR4-3200", "approx_price": 40},
            {"component": "Storage", "brand": "Crucial", "model": "P3 1TB NVMe", "approx_price": 60},
            {"component": "PSU", "brand": "EVGA", "model": "450 BR 80+ Bronze", "approx_price": 50},
            {"component": "Case", "brand": "Fractal Design", "model": "Focus G", "approx_price": 60},
        ],
    },
}