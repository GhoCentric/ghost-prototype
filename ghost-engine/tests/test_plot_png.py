from ghost import GhostAPI

# -----------------------------
# SIMPLE PNG WRITER (NO LIBS)
# -----------------------------
def save_png(filename, width, height, pixels):
    import zlib, struct

    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
        )

    raw = b""
    for y in range(height):
        raw += b"\x00"
        for (r, g, b) in pixels[y]:
            raw += bytes([r, g, b])

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")

    with open(filename, "wb") as f:
        f.write(png)


# -----------------------------
# TEST SEQUENCE (REAL SCENARIO)
# -----------------------------
def get_sequence():
    return [
        ("help", 0.4),
        ("help", 0.4),
        ("help", 0.4),

        ("insult", 0.9),  # betrayal spike

        ("help", 0.3),
        ("help", 0.3),

        ("insult", 0.6),
        ("insult", 0.6),

        ("help", 0.5),
        ("help", 0.5),
    ]


# -----------------------------
# RUN GHOST
# -----------------------------
def run_ghost():
    ghost = GhostAPI()
    results = []

    for event, intensity in get_sequence():
        ghost.apply_event("A", "B", {
            "type": event,
            "intensity": intensity
        })

        rel = ghost.get_relationship("A", "B")
        results.append(rel["trust"])

    return results


# -----------------------------
# BASELINE (NO MEMORY)
# -----------------------------
def run_baseline():
    trust = 0.0
    results = []

    alpha = 0.3

    for event, intensity in get_sequence():
        val = intensity if event == "help" else -intensity

        trust = trust * (1 - alpha) + val * alpha
        trust = max(min(trust, 1.0), -1.0)

        results.append(trust)

    return results


# -----------------------------
# GRAPH
# -----------------------------
def draw_graph(data_sets):
    width = 800
    height = 400
    padding = 60

    plot_w = width - padding * 2
    plot_h = height - padding * 2

    pixels = [[(255, 255, 255) for _ in range(width)] for _ in range(height)]

    # scale
    min_val = -1.0
    max_val = 1.0
    rng = max_val - min_val

    def to_screen(i, val, n):
        x = padding + int(i * (plot_w / (n - 1)))
        y = padding + int((1 - (val - min_val) / rng) * plot_h)
        return x, y

    # grid
    for i in range(5):
        y = padding + int(i * (plot_h / 4))
        for x in range(padding, padding + plot_w):
            pixels[y][x] = (220, 220, 220)

    # axes
    for y in range(padding, padding + plot_h):
        pixels[y][padding] = (0, 0, 0)

    zero_y = padding + int(plot_h / 2)
    for x in range(padding, padding + plot_w):
        pixels[zero_y][x] = (180, 180, 180)

    # line drawing
    def draw_line(x0, y0, x1, y1, color):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy

        while True:
            if 0 <= x0 < width and 0 <= y0 < height:
                pixels[y0][x0] = color

            if x0 == x1 and y0 == y1:
                break

            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    colors = [
        (0, 0, 0),       # baseline
        (0, 100, 255),   # ghost
    ]

    for data, color in zip(data_sets, colors):
        prev = None
        n = len(data)

        for i, val in enumerate(data):
            x, y = to_screen(i, val, n)

            if prev is not None:
                x0, y0 = prev
                draw_line(x0, y0, x, y, color)
                
            prev = (x, y)

    return pixels, width, height


# -----------------------------
# MAIN
# -----------------------------
def main():
    baseline = run_baseline()
    ghost = run_ghost()

    pixels, w, h = draw_graph([baseline, ghost])

    import time
    filename = f"ghost_plot_{int(time.time())}.png"
    save_png(filename, w, h, pixels)
    print(f"\nSaved: {filename}")


if __name__ == "__main__":
    main()


def test_plot_png_contract(tmp_path):
    baseline = run_baseline()
    ghost = run_ghost()

    assert len(baseline) == len(get_sequence())
    assert len(ghost) == len(get_sequence())
    assert baseline != ghost

    for series in (baseline, ghost):
        for value in series:
            assert -5.0 <= value <= 5.0

    pixels, width, height = draw_graph([baseline, ghost])

    assert width > 0
    assert height > 0
    assert len(pixels) == height
    assert len(pixels[0]) == width

    filename = tmp_path / "ghost_plot_test.png"
    save_png(str(filename), width, height, pixels)

    data = filename.read_bytes()

    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"IHDR" in data
    assert b"IDAT" in data
    assert b"IEND" in data
