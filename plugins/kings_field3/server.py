"""Thin native-port service registration for King's Field III."""
from core.native_port_http import serve
from .model import MODEL

if __name__ == "__main__":
    serve(MODEL, __file__)
