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
    "1080_entry": {
        "label": "Entry level 1080p",
        "description": "Solid 1080p performance for popular titles without breaking the bank.",
        "total_approx": 1100,
        "parts": [
            {"component": "CPU", "brand": "AMD", "model": "Ryzen 5 5500", "approx_price": 85},
            {"component": "CPU Cooler", "brand": "Thermalright", "model": "Assassin 120 SE", "approx_price": 35},
            {"component": "Motherboard", "brand": "Gigabyte", "model": "B550 Eagle", "approx_price": 100},
            {"component": "RAM", "brand": "Corsair", "model": "Vengeance 16GB DDR4", "approx_price": 140},
            {"component": "Storage", "brand": "Samsung", "model": "990 Pro 1TB", "approx_price": 200},
            {"component": "GPU", "brand": "AMD", "model": "Radeon RX 7600", "approx_price": 300},
            {"component": "PSU", "brand": "Corsair", "model": "RM 650e", "approx_price": 80},
            {"component": "Case", "brand": "NZXT", "model": "H5", "approx_price": 100},
        ],
    },
    "1080_competitive": {
        "label": "Competitive 1080p",
        "description": "240+ FPS at 1080p from most popular FPS titles.",
        "total_approx": 2700,
        "parts": [
            {"component": "CPU", "brand": "AMD", "model": "Ryzen 9 9950X3D", "approx_price": 550},
            {"component": "CPU Cooler", "brand": "Corsair", "model": "iCUE Titan 360", "approx_price": 160},
            {"component": "Motherboard", "brand": "Gigabyte", "model": "B850 AORUS Elite", "approx_price": 210},
            {"component": "RAM", "brand": "Corsair", "model": "Vengeance RGB 32GB DDR5", "approx_price": 400},
            {"component": "Storage", "brand": "Samsung", "model": "990 Pro 2TB", "approx_price": 330},
            {"component": "GPU", "brand": "Nvidia", "model": "RTX 5070", "approx_price": 650},
            {"component": "PSU", "brand": "Corsair", "model": "RM 1000x", "approx_price": 180},
            {"component": "Case", "brand": "Corsair", "model": "5000D", "approx_price": 180},
        ],
    },
    "1440_mid": {
        "label": "Mid level 1440p",
        "description": "Solid 1440p performance for popular titles at high settings.",
        "total_approx": 2000,
        "parts": [
            {"component": "CPU", "brand": "AMD", "model": "Ryzen 5 7600X", "approx_price": 180},
            {"component": "CPU Cooler", "brand": "Thermalright", "model": "Assassin 120 SE RGB", "approx_price": 40},
            {"component": "Motherboard", "brand": "Gigabyte", "model": "B850 AORUS Elite", "approx_price": 210},
            {"component": "RAM", "brand": "Corsair", "model": "Vengeance RGB 32GB DDR5", "approx_price": 400},
            {"component": "Storage", "brand": "Samsung", "model": "990 Pro 2TB", "approx_price": 330},
            {"component": "GPU", "brand": "Nvidia", "model": "RTX 5070", "approx_price": 650},
            {"component": "PSU", "brand": "Corsair", "model": "RM850e", "approx_price": 125},
            {"component": "Case", "brand": "NZXT", "model": "H5", "approx_price": 80},
        ],
    },
    "1440_uppermid": {
        "label": "Upper mid level 1440p",
        "description": "Solid 1440p performance for FPS titles (144+ FPS) and access to latest AAA titles.",
        "total_approx": 2700,
        "parts": [
            {"component": "CPU", "brand": "AMD", "model": "Ryzen 7 9700X", "approx_price": 300},
            {"component": "CPU Cooler", "brand": "Corsair", "model": "iCUE Titan 240", "approx_price": 140},
            {"component": "Motherboard", "brand": "Gigabyte", "model": "B850 AORUS Elite", "approx_price": 210},
            {"component": "RAM", "brand": "Corsair", "model": "Vengeance RGB 32GB DDR5", "approx_price": 400},
            {"component": "Storage", "brand": "Samsung", "model": "990 Pro 2TB", "approx_price": 330},
            {"component": "GPU", "brand": "Nvidia", "model": "RTX 5070 Ti", "approx_price": 1000},
            {"component": "PSU", "brand": "Corsair", "model": "RM850e", "approx_price": 125},
            {"component": "Case", "brand": "Corsair", "model": "5000D", "approx_price": 180},
        ],
    },
    "1440_creator": {
        "label": "Creator 1440p",
        "description": "Able to breeze through virtually any title at 1440p while streaming and edit the videos later.",
        "total_approx": 4800,
        "parts": [
            {"component": "CPU", "brand": "Intel", "model": "Ultra 9 285K", "approx_price": 550},
            {"component": "CPU Cooler", "brand": "Corsair", "model": "iCUE Titan 360", "approx_price": 180},
            {"component": "GPU", "brand": "Nvidia", "model": "RTX 5080", "approx_price": 1600},
            {"component": "Motherboard", "brand": "Asus", "model": "ProArt Z890-Creator", "approx_price": 450},
            {"component": "RAM", "brand": "Corsair", "model": "Vengeance 64GB DDR5 6000MHz", "approx_price": 1000},
            {"component": "Storage", "brand": "Samsung", "model": "990 Pro 4TB NVMe SSD", "approx_price": 660},
            {"component": "PSU", "brand": "Corsair", "model": "RM1000x", "approx_price": 180},
            {"component": "Case", "brand": "Corsair", "model": "5000D", "approx_price": 180},
        ],
    },
    "1440_competitive": {
        "label": "Competitive 1440p",
        "description": "240+ FPS at 1440p from most popular FPS titles.",
        "total_approx": 3600,
        "parts": [
            {"component": "CPU", "brand": "AMD", "model": "Ryzen 9 9950X3D", "approx_price": 550},
            {"component": "CPU Cooler", "brand": "Corsair", "model": "iCUE Titan 360", "approx_price": 160},
            {"component": "Motherboard", "brand": "Gigabyte", "model": "B850 AORUS Elite", "approx_price": 210},
            {"component": "RAM", "brand": "Corsair", "model": "Vengeance RGB 32GB DDR5", "approx_price": 400},
            {"component": "Storage", "brand": "Samsung", "model": "990 Pro 2TB", "approx_price": 330},
            {"component": "GPU", "brand": "Nvidia", "model": "RTX 5080", "approx_price": 1600},
            {"component": "PSU", "brand": "Corsair", "model": "RM 1000x", "approx_price": 180},
            {"component": "Case", "brand": "Corsair", "model": "5000D", "approx_price": 180},
        ],
    },
    "1440_localllm": {
        "label": "Local LLM 1440p",
        "description": "1440p machine designed to inference and lightly fine-tune ML models and play competitive FPS games at 240 FPS, or AAA titles at 60+ FPS on high graphics.",
        "total_approx": 3700,
        "parts": [
            {"component": "CPU", "brand": "AMD", "model": "Ryzen 7 9700X", "approx_price": 300},
            {"component": "CPU Cooler", "brand": "Corsair", "model": "iCue Titan 360", "approx_price": 160},
            {"component": "Motherboard", "brand": "Gigabyte", "model": "B850 AORUS Elite", "approx_price": 210},
            {"component": "RAM", "brand": "Corsair", "model": "Vengeance 64GB DDR5 6000MHz", "approx_price": 1000},
            {"component": "Storage", "brand": "Samsung", "model": "990 Pro 4TB NVMe SSD", "approx_price": 660},
            {"component": "GPU", "brand": "Nvidia", "model": "RTX 3090 (used)", "approx_price": 1000},
            {"component": "PSU", "brand": "Corsair", "model": "RM1000x", "approx_price": 180},
            {"component": "Case", "brand": "Corsair", "model": "5000D", "approx_price": 180},
        ],
    },
    "2160_cinematic": {
        "label": "Cinematic 4k",
        "description": "4k build able to play the latest AAA titles at 60+ FPS.",
        "total_approx": 3900,
        "parts": [
            {"component": "CPU", "brand": "AMD", "model": "Ryzen 7 9800X3D", "approx_price": 450},
            {"component": "CPU Cooler", "brand": "Corsair", "model": "iCue Titan 360", "approx_price": 160},
            {"component": "GPU", "brand": "Nvidia", "model": "RTX 5080", "approx_price": 1600},
            {"component": "Motherboard", "brand": "Gigabyte", "model": "B850 AORUS Elite", "approx_price": 210},
            {"component": "RAM", "brand": "Corsair", "model": "Vengeance 32GB DDR5 6000MHz", "approx_price": 400},
            {"component": "Storage", "brand": "Samsung", "model": "990 Pro 4TB NVMe SSD", "approx_price": 660},
            {"component": "PSU", "brand": "Corsair", "model": "RM1000x", "approx_price": 180},
            {"component": "Case", "brand": "Corsair", "model": "5000D", "approx_price": 180},
        ],
    },
    "2160_creator": {
        "label": "Creator 4k",
        "description": "4k build for playing the latest AAA titles and streaming/editing in 4k.",
        "total_approx": 5000,
        "parts": [
            {"component": "CPU", "brand": "Intel", "model": "Ultra 9 285K", "approx_price": 550},
            {"component": "CPU Cooler", "brand": "NZXT", "model": "Kraken Elite 360", "approx_price": 250},
            {"component": "GPU", "brand": "Nvidia", "model": "RTX 5080", "approx_price": 1600},
            {"component": "Motherboard", "brand": "Asus", "model": "ProArt Z890-Creator", "approx_price": 450},
            {"component": "RAM", "brand": "Corsair", "model": "Vengeance 64GB DDR5 6000MHz", "approx_price": 1000},
            {"component": "Storage", "brand": "Samsung", "model": "990 Pro 4TB NVMe SSD", "approx_price": 660},
            {"component": "PSU", "brand": "Corsair", "model": "RM1000x", "approx_price": 180},
            {"component": "Case", "brand": "NZXT", "model": "H9", "approx_price": 250},
        ],
    },
    "2160_localllm": {
        "label": "Local LLM 4k",
        "description": "Local LLM machine for models of around 35B parameters and an elite 4K gaming computer.",
        "total_approx": 7000,
        "parts": [
            {"component": "CPU", "brand": "AMD", "model": "Ryzen 7 9700X", "approx_price": 300},
            {"component": "CPU Cooler", "brand": "NZXT", "model": "Kraken Elite 360", "approx_price": 250},
            {"component": "Motherboard", "brand": "ASUS", "model": "TUF X870E-PLUS", "approx_price": 300},
            {"component": "RAM", "brand": "Corsair", "model": "Vengeance 64GB DDR5 6000MHz", "approx_price": 1000},
            {"component": "Storage", "brand": "Samsung", "model": "990 Pro 4TB NVMe SSD", "approx_price": 660},
            {"component": "GPU", "brand": "Nvidia", "model": "RTX 5090", "approx_price": 4000},
            {"component": "PSU", "brand": "Corsair", "model": "RM1200x", "approx_price": 200},
            {"component": "Case", "brand": "NZXT", "model": "H9", "approx_price": 250},
        ],
    },
    "2160_localllmpro": {
        "label": "Local LLM Pro 4k",
        "description": "Local LLM machine for models of around 70B parameters.",
        "total_approx": 12000,
        "parts": [
            {"component": "CPU", "brand": "AMD", "model": "Ryzen 7 9700X", "approx_price": 300},
            {"component": "CPU Cooler", "brand": "NZXT", "model": "Kraken Elite 360", "approx_price": 250},
            {"component": "Motherboard", "brand": "ASUS", "model": "TUF X870E-PLUS", "approx_price": 300},
            {"component": "RAM", "brand": "Corsair", "model": "Vengeance 64GB DDR5 6000MHz", "approx_price": 1000},
            {"component": "Storage", "brand": "Samsung", "model": "990 Pro 4TB NVMe SSD", "approx_price": 660},
            {"component": "GPU", "brand": "Nvidia", "model": "RTX PRO 6000 Blackwell", "approx_price": 9000},
            {"component": "PSU", "brand": "Corsair", "model": "RM1200x", "approx_price": 200},
            {"component": "Case", "brand": "NZXT", "model": "H9", "approx_price": 250},
        ],
    },
}