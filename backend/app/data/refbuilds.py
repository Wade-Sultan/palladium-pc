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
        "description": "Solid 1080p performance for popular titles at high settings without breaking the bank.",
        "total_approx": 1000,
        "parts": [
            {"component": "CPU", "brand": "AMD", "model": "Ryzen 5 5600", "approx_price": 160},
            {"component": "CPU Cooler", "brand": "", "model": "Ryzen 5 5600", "approx_price": 160},
            {"component": "GPU", "brand": "AMD", "model": "Radeon RX 7600", "approx_price": 300},
            {"component": "Motherboard", "brand": "MSI", "model": "B550M PRO-VDH WiFi", "approx_price": 100},
            {"component": "RAM", "brand": "G.Skill", "model": "Ripjaws V 16GB DDR4-3600", "approx_price": 160},
            {"component": "Storage", "brand": "Samsung", "model": "870 EVO 1TB SATA SSD", "approx_price": 180},
            {"component": "PSU", "brand": "Thermaltake", "model": "550 G6 80+ Gold", "approx_price": 70},
            {"component": "Case", "brand": "Fractal Design", "model": "Pop Air", "approx_price": 80},
            {"component": "Fans", "brand": "AMD", "model": "Ryzen 5 5600", "approx_price": 160},
        ],
    },
    "1080_mid": {
        "label": "Mid level 1080p",
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
    "1080_competitive": {
        "label": "Competitive 1080p",
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
    "1440_mid": {
        "label": "Mid level 1440p",
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
    "1440_uppermid": {
        "label": "Upper mid level 1440p",
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
    "1440_creator": {
        "label": "Creator 1440p",
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
    "1440_competitive": {
        "label": "Competitive 1440p",
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
    "1440_localllm": {
        "label": "Local LLM 1440p",
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
    "2160_cinematic": {
        "label": "Cinematic 4k",
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
    "2160_creator": {
        "label": "Creator 4k",
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
    "2160_localllm": {
        "label": "Local LLM 4k",
        "description": "Local LLM machine for models of around 35B parameters and an elite 4K gaming computer.",
        "total_approx": 7000,
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
    "2160_localllmpro": {
        "label": "Local LLM Pro 4k",
        "description": "Local LLM machine for models of around 70B parameters.",
        "total_approx": 12000,
        "parts": [
            {"component": "CPU", "brand": "AMD", "model": "Ryzen 7 9700X", "approx_price": 300},
            {"component": "CPU Cooler", "brand": "NZXT", "model": "Kraken Elite 360", "approx_price": 250},
            {"component": "GPU", "brand": "Nvidia", "model": "RTX PRO 6000 Blackwell", "approx_price": 9000},
            {"component": "Motherboard", "brand": "Gigabyte", "model": "B550M PRO-VDH WiFi", "approx_price": 210},
            {"component": "RAM", "brand": "Corsair", "model": "Ripjaws V 16GB DDR4-3600", "approx_price": 1000},
            {"component": "Storage", "brand": "Samsung", "model": "990 Pro 4TB NVMe SSD", "approx_price": 660},
            {"component": "PSU", "brand": "Corsair", "model": "RM1200x", "approx_price": 200},
            {"component": "Case", "brand": "NZXT", "model": "H9", "approx_price": 250},
        ],
    },
}