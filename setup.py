"""Setup script for Claude Code Local Tracing."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="claude-trace",
    version="0.1.0",
    author="Claude Trace Contributors",
    description="Local tracing solution for Claude Code CLI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Dtristone/tracing-claude-code-local",
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.8",
    install_requires=[
        # No external dependencies required for core functionality
        # SQLite is built into Python
    ],
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-cov>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "claude-trace=claude_trace.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Debuggers",
        "Topic :: System :: Monitoring",
    ],
    keywords="claude, tracing, monitoring, debugging, llm",
)
