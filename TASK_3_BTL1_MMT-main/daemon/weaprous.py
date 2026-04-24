from backend import create_backend
class WeApRous:
    def __init__(self):
        self.routes = {}

    def route(self, path, methods=["GET"]):
        def decorator(func):
            self.routes[path] = func
            return func
        return decorator

    def prepare_address(self, ip, port):
        self.ip = ip
        self.port = port

    def run(self):
        create_backend(self.ip, self.port, self.routes)
