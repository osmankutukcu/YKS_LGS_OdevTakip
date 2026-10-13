"""Experimental, explicitly opt-in Windows style refresh coalescing.

Never import this from the normal application. Used only in a disposable-db pilot.
"""
from .refresh import RefreshGate, install_experimental_style_coalescing

__all__ = ['RefreshGate', 'install_experimental_style_coalescing']
