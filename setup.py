from setuptools import find_packages, setup


setup(
    name="intraday-investment-monitor",
    version="0.1.0",
    description="Local-only intraday investment monitoring and suggestion app",
    packages=find_packages(include=["backend", "backend.*"]),
    include_package_data=True,
    python_requires=">=3.9",
    extras_require={
        "api": [
            "fastapi>=0.110",
            "uvicorn>=0.27",
        ],
        "ibkr": [
            "ib_insync>=0.9.86",
        ],
        "test": [
            "pytest>=8",
            "pytest-asyncio>=0.23",
            "httpx>=0.27",
        ],
    },
)

