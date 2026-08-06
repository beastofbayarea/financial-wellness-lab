"""Shared utilities for the Financial Wellness Lab.

This package contains cross-cutting modules used by multiple components:

- **narrator**: Optional LLM-based explanation layer that converts structured
  decision outputs into human-readable text. Falls back gracefully to
  deterministic templates when unavailable.

The narrator enforces a strict boundary: it receives only pre-computed reason
codes and allowlisted facts, never raw user data or decision inputs. This
ensures the language model can explain decisions but cannot influence them.
"""
