"""Diagram as code: regenerates docs/diagrams/architecture.svg (and .png if cairosvg is installed).

    python3 docs/diagrams/generate_architecture.py
"""

from pathlib import Path
from xml.sax.saxutils import escape

W, H = 1600, 1000
FONT = "Inter, 'Helvetica Neue', Helvetica, Arial, sans-serif"

COLORS = {
    "compute": "#ED7100",
    "storage": "#7AA116",
    "integration": "#E7157B",
    "database": "#C925D1",
    "network": "#8C4FFF",
    "client": "#232F3E",
}
INK, MUTED, LINE, RED = "#16191F", "#545B64", "#545B64", "#D13212"

out: list[str] = []


def text(x, y, s, size=13, weight=400, color=INK, anchor="start", italic=False):
    style = ' font-style="italic"' if italic else ""
    out.append(
        f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}" '
        f'text-anchor="{anchor}"{style}>{escape(s)}</text>'
    )


def node(x, y, w, h, title, sub, kind):
    c = COLORS[kind]
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="#FFFFFF" stroke="{c}" stroke-width="1.6"/>')
    out.append(f'<rect x="{x}" y="{y}" width="8" height="{h}" rx="3" fill="{c}"/>')
    cy = y + h / 2
    text(x + 18, cy - (2 if sub else -5), title, 14, 700)
    if sub:
        text(x + 18, cy + 15, sub, 11.5, 400, MUTED)


def box(x, y, w, h, label, stroke, dash="", fill="none", label_color=None, size=13):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1.4"{d}/>')
    if label:
        text(x + 14, y + 22, label, size, 700, label_color or stroke)


def arrow(points, dashed=False, color=LINE):
    d = " ".join(f"{'M' if i == 0 else 'L'}{x},{y}" for i, (x, y) in enumerate(points))
    dash = ' stroke-dasharray="6 5"' if dashed else ""
    out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.6"{dash} marker-end="url(#arrow)"/>')


def step(x, y, n, label="", anchor="start"):
    out.append(f'<circle cx="{x}" cy="{y}" r="10" fill="#232F3E"/>')
    text(x, y + 4.5, str(n), 11.5, 700, "#FFFFFF", "middle")
    if label:
        dx = 15 if anchor == "start" else -15
        text(x + dx, y + 4.5, label, 12, 500, INK, anchor)


# ---------------------------------------------------------------- frame
out.append(f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>')
text(30, 52, "Serverless Image Processing Pipeline", 22, 800)
text(30, 74, "S3 · SQS · Lambda · Step Functions · API Gateway · DynamoDB · CloudFront · SNS", 12.5, 400, MUTED)

box(210, 95, 1370, 790, "AWS Cloud — region eu-west-3 (Paris)", "#232F3E", fill="#FAFAFA")

# ---------------------------------------------------------------- client
node(30, 330, 140, 90, "Client", "browser · curl", "client")

# ---------------------------------------------------------------- API layer
node(260, 150, 190, 70, "API Gateway", "HTTP API · throttled", "network")
node(520, 120, 190, 60, "λ presign", "POST /uploads", "compute")
node(520, 200, 190, 60, "λ get_image", "GET /images/{id}", "compute")
node(790, 155, 200, 70, "DynamoDB", "images · GSI · TTL · PITR", "database")

# ---------------------------------------------------------------- ingest
node(260, 330, 190, 70, "S3 source bucket", "uploads/ · private · lifecycle", "storage")
node(520, 330, 190, 70, "SQS queue", "uploads · long polling", "integration")
node(520, 470, 190, 60, "SQS dead-letter queue", "14-day retention", "integration")
node(790, 330, 170, 70, "λ dispatcher", "partial batch failures", "compute")

# ---------------------------------------------------------------- workflow
box(1000, 250, 560, 360, "Step Functions — Standard workflow", COLORS["integration"], fill="#FFFFFF")
node(1020, 290, 160, 50, "MarkProcessing", "DynamoDB UpdateItem", "database")
node(1020, 370, 160, 50, "λ validate", "format · size · bomb", "compute")
box(1200, 278, 172, 160, "Parallel", MUTED, dash="5 4", size=11.5)
node(1211, 308, 150, 50, "λ thumbnail", "256 px JPEG", "compute")
node(1211, 376, 150, 50, "λ watermark", "1920 px + text", "compute")
node(1392, 290, 150, 50, "RecordSuccess", "status COMPLETED", "database")
node(1392, 370, 150, 50, "NotifySuccess", "SNS Publish", "integration")

out.append('<rect x="1020" y="450" width="352" height="22" rx="11" fill="#FFF4E5" stroke="#ED7100" stroke-width="1"/>')
text(1196, 465, "Pillow Lambda Layer · arm64 · Python 3.13", 11.5, 600, "#8A4B00", "middle")

box(1020, 484, 420, 112, "", RED, dash="4 3", fill="#FFF8F7")
text(1034, 506, "Error handling", 12.5, 700, RED)
text(1034, 528, "Lambda transient errors → Retry ×3, exponential backoff + jitter", 11.5, 400, INK)
text(1034, 549, "InvalidImageError → RecordRejected → NotifyRejected → Succeed", 11.5, 400, INK)
text(1034, 570, "Anything else → RecordFailure → NotifyFailure → Fail (alarm)", 11.5, 400, INK)
text(1034, 588, "status: REJECTED (user error) vs FAILED (system error)", 11, 400, MUTED, italic=True)

# ---------------------------------------------------------------- delivery + notifications
node(260, 680, 190, 70, "CloudFront", "OAC · HTTPS · edge cache", "network")
node(1000, 680, 210, 70, "S3 processed bucket", "thumbnails/ · full/ · private", "storage")
node(1360, 680, 190, 70, "SNS image-events", "per-image job events", "integration")

# ---------------------------------------------------------------- observability
node(520, 790, 210, 70, "CloudWatch", "logs · alarms · dashboard", "integration")
node(800, 790, 170, 70, "SNS alerts", "ops notifications", "integration")
node(1290, 925, 190, 50, "Email subscriber", "", "client")

# ---------------------------------------------------------------- arrows
# 1 + 9: API calls
arrow([(170, 350), (228, 350), (228, 185), (260, 185)])
step(242, 270, 1)
text(254, 266, "POST /uploads", 11.5, 500)
step(242, 300, 9)
text(254, 296 + 8, "GET /images/{id}", 11.5, 500)
arrow([(450, 175), (485, 175), (485, 150), (520, 150)])
arrow([(450, 195), (485, 195), (485, 230), (520, 230)])
arrow([(710, 150), (750, 150), (750, 175), (790, 175)])
arrow([(710, 230), (750, 230), (750, 205), (790, 205)])
text(716, 142, "PutItem", 11, 500, MUTED)
text(716, 250, "GetItem", 11, 500, MUTED)

# 2: direct upload
arrow([(170, 395), (260, 395)])
step(232, 440, 2, "presigned POST")
text(247, 458, "direct to S3", 11, 400, MUTED)

# 3, 4: event to queue to dispatcher
arrow([(450, 365), (520, 365)])
step(485, 318, 3)
text(462, 305, "ObjectCreated", 11, 500, MUTED)
arrow([(710, 365), (790, 365)])
step(750, 318, 4)
text(734, 305, "batch ≤ 10", 11, 500, MUTED)
arrow([(615, 400), (615, 470)], dashed=True, color=RED)
text(625, 442, "after 3 failed receives", 11, 500, RED)

# 5: start execution
arrow([(960, 365), (980, 365), (980, 315), (1020, 315)])
step(820, 428, 5, "StartExecution")
text(835, 452, "name = imageId (dedupe)", 11, 400, MUTED)

# workflow internals
arrow([(1100, 340), (1100, 370)])
arrow([(1180, 395), (1200, 395)])
arrow([(1372, 315), (1392, 315)])
arrow([(1467, 340), (1467, 370)])

# 6: read original / write results
arrow([(355, 400), (355, 640), (1040, 640), (1040, 610)], dashed=True)
step(700, 640, 6)
text(716, 632, "GetObject original", 11.5, 500)
arrow([(1105, 610), (1105, 680)])
text(1115, 650, "PutObject thumbnails/ · full/", 11.5, 500)

# 7: workflow status in DynamoDB
arrow([(1500, 250), (1500, 120), (890, 120), (890, 155)])
step(1120, 120, 7)
text(1136, 142, "status PROCESSING → COMPLETED | REJECTED | FAILED", 11.5, 500)

# 8: notifications
arrow([(1467, 420), (1467, 470), (1500, 470), (1500, 680)])
step(1500, 645, 8, "Publish", anchor="end")
arrow([(1455, 750), (1455, 925)])
arrow([(970, 825), (1385, 825), (1385, 925)])
arrow([(730, 825), (800, 825)])
text(735, 815, "alarm", 11, 500, MUTED)

# 10: delivery
arrow([(1000, 715), (450, 715)])
text(600, 707, "Origin Access Control (SigV4)", 11.5, 500, MUTED)
arrow([(260, 715), (100, 715), (100, 420)])
step(100, 560, 10, "HTTPS GET", anchor="start")
text(115, 582, "edge-cached", 11, 400, MUTED)

# ---------------------------------------------------------------- legend
lx, ly = 30, 925
text(lx, ly - 6, "Legend", 12.5, 700)
items = [("Compute", "compute"), ("Storage", "storage"), ("Integration / Mgmt", "integration"),
         ("Database", "database"), ("Networking / CDN", "network")]
for i, (label, kind) in enumerate(items):
    x = lx + (i % 3) * 170
    y = ly + 8 + (i // 3) * 24
    out.append(f'<rect x="{x}" y="{y}" width="14" height="14" rx="3" fill="{COLORS[kind]}"/>')
    text(x + 20, y + 11.5, label, 12, 500)
out.append(f'<path d="M{lx + 510},{ly + 15} L{lx + 560},{ly + 15}" stroke="{LINE}" stroke-width="1.6" stroke-dasharray="6 5" marker-end="url(#arrow)"/>')
text(lx + 568, ly + 19, "data read / failure path", 12, 500)

# ---------------------------------------------------------------- write
svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">'
    '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
    f'<path d="M0,0 L10,5 L0,10 z" fill="{LINE}"/></marker></defs>'
    + "".join(out)
    + "</svg>"
)
here = Path(__file__).parent
(here / "architecture.svg").write_text(svg, encoding="utf-8")
try:
    import cairosvg

    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(here / "architecture.png"), output_width=W * 2)
    print("Wrote architecture.svg and architecture.png")
except ImportError:
    print("Wrote architecture.svg (pip install cairosvg to also export a PNG)")
