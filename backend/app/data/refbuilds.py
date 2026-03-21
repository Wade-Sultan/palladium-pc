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
            {"component": "GPU", "brand": "AMD", "model": "Radeon RX 7600", "approx_price": 300},
            {"component": "Motherboard", "brand": "MSI", "model": "B550M PRO-VDH WiFi", "approx_price": 100},
            {"component": "RAM", "brand": "G.Skill", "model": "Ripjaws V 16GB DDR4-3600", "approx_price": 160},
            {"component": "Storage", "brand": "Samsung", "model": "870 EVO 1TB SATA SSD", "approx_price": 180},
            {"component": "PSU", "brand": "Thermaltake", "model": "550 G6 80+ Gold", "approx_price": 70},
            {"component": "Case", "brand": "Fractal Design", "model": "Pop Air", "approx_price": 80},
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
    "1440_uppermid": {
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
    "1440_creator": {
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
    "1440_competitive": {
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
    "2160_cinematic": {
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
    "2160_creator": {
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
    "2160_localllm": {
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
    "2160_localllmpro": {
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
}