"""讓根目錄 unittest discovery 納入面板測試，保留直接執行的匯入名稱。"""
import sys

from . import build_dashboard

sys.modules.setdefault("build_dashboard", build_dashboard)
