from daemon.weaprous import WeApRous
app = WeApRous()

@app.route("/")
def index(req):
    return "Backend 1"

if __name__ == "__main__":
    app.prepare_address("0.0.0.0", 9001)
    app.run()