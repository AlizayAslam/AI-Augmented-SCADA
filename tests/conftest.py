"""
conftest.py — shared pytest configuration and fixtures
"""
import sys, os

# Ensure project root is on sys.path so `import core.*` works from tests/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
