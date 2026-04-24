class Request:
    def __init__(self, raw):
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        
        lines = raw.split("\r\n")
        parts = lines[0].split(" ")
        self.method = parts[0] if len(parts) > 0 else ""
        self.path = parts[1] if len(parts) > 1 else "/"
        self.headers = {}
        self.body = ""  

        i = 1
        while i < len(lines):
            line = lines[i]
            if line == "":
                self.body = "\r\n".join(lines[i+1:])
                break
            if ":" in line:
                k, v = line.split(":", 1)
                self.headers[k.strip().lower()] = v.strip()
            i += 1
