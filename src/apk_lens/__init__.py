"""apk-lens — educational static analysis for Android app bundles.

The package is deliberately layered so that each stage can be run — and read —
on its own:

    acquire  -> unpack -> decompile -> scan -> report

Nothing here runs the app under analysis. Every finding describes a capability
present in the code, which is not the same thing as a behaviour observed on the
wire. The report layer is responsible for keeping that distinction visible.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
