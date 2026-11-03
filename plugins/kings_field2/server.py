"""KF2 settings and metadata through the shared native-port loopback service."""
from core.native_port_http import serve
from .model import MODEL

if __name__ == "__main__":
    serve(MODEL, __file__)
