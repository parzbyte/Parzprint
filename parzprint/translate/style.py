"""Folha de estilo da janela do tradutor, sobre a do painel de texto."""

from __future__ import annotations

from .. import brand
from ..textpanel import PANEL_STYLE

STYLE = PANEL_STYLE + f"""
QComboBox {{ background: {brand.SURFACE_2}; color: #F2F2F2; border: 1px solid {brand.BORDER};
             border-radius: 6px; padding: 4px 8px; min-width: 150px; }}
QComboBox QAbstractItemView {{ background: {brand.SURFACE_2}; color: #F2F2F2;
                               selection-background-color: {brand.RED}; }}
QPushButton#flat {{ background: transparent; border: none; padding: 2px 8px; font-size: 14px; }}
QPushButton#flat:hover {{ background: {brand.SURFACE_3}; }}
QPushButton#flat:checked {{ background: {brand.RED}; color: #FFFFFF; }}
"""
