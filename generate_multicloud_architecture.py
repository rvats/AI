from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont


WIDTH = 2800
HEIGHT = 2200
OUTPUT_PATHS = [
    Path(__file__).with_name("AgenticAIArchitecture_MultiCloud.jpg"),
    Path(__file__).with_name("AgenticAIArchitecture.jpg"),
]


TERMINOLOGY_GROUPS = [
    (
        "Languages & Full Stack",
        "Python, TypeScript, JavaScript, C#/.NET, Java, C/C++; React, Next.js, Node.js, FastAPI, Spring Boot, ASP.NET; REST, GraphQL, gRPC, WebSockets",
    ),
    (
        "AI-Assisted SDLC",
        "Cursor, Claude Code, GitHub Copilot, Anthropic Claude API, MCP (Model Context Protocol), AI pair-programming, AI code-review automation, AI test generation",
    ),
    (
        "Agentic AI & GenAI",
        "Multi-agent orchestration (AutoGen, LangGraph, CrewAI), tool-use & function-calling, planner/executor patterns, agentic RAG, ReAct, vector DBs (Pinecone, pgvector, Weaviate, OpenSearch), embeddings, prompt engineering, eval harnesses, guardrails",
    ),
    (
        "LLM Platforms",
        "Anthropic Claude, OpenAI / Azure OpenAI, AWS Bedrock, Llama, Mistral; RAG, retrieval orchestration, model routing, cost & latency optimization",
    ),
    (
        "AWS Cloud-Native",
        "Lambda, ECS, EKS, API Gateway, S3, DynamoDB, RDS/Aurora, EventBridge, SQS, SNS, Step Functions, CloudWatch, Bedrock, SageMaker, OpenSearch, IAM",
    ),
    (
        "Azure & GCP",
        "Azure (AKS, OpenAI, Functions, Cosmos DB, Service Bus, Key Vault, App Insights, Document Intelligence); GCP (Vertex AI, Gemini, GKE, Pub/Sub, BigQuery)",
    ),
    (
        "IaC & Containers",
        "Terraform (primary), AWS CDK, CloudFormation, Bicep, Helm; Docker, Kubernetes (EKS, AKS, GKE), Istio, AWS Fargate, Knative",
    ),
    (
        "DevSecOps & CI/CD",
        "GitHub Actions, GitLab CI, Jenkins, ArgoCD, Twelve-Factor App, trunk-based dev; SAST, DAST, dependency & secret scanning, OWASP Top 10",
    ),
    (
        "Architecture Patterns",
        "Microservices, Serverless, Event-Driven, Domain-Driven Design (DDD), Hexagonal/Ports-and-Adapters, CQRS, Saga, API-first design",
    ),
    (
        "Data & Graph",
        "PostgreSQL, MySQL, MongoDB, Neo4j (Cypher, GDS, Causal Cluster), Snowflake, Spark/PySpark, Kafka, Airflow, GraphQL, Databricks",
    ),
    (
        "Forward Deployed & Consulting",
        "Embedded delivery, technical adoption playbooks, change management, executive stakeholder communication, mentoring & upskilling, rapid onboarding, influencing without formal authority",
    ),
    (
        "Security & Governance",
        "Threat modeling, secure SDLC, RBAC, encryption at rest/in transit; AI/LLM security (prompt-injection mitigation, guardrails, model governance); HIPAA, GDPR, FDA 21 CFR Part 11, SOC 2",
    ),
]


MULTICLOUD_ROWS = [
    ("LLM / AI", "Bedrock, SageMaker", "Azure OpenAI, Document Intelligence", "Vertex AI, Gemini"),
    ("Compute", "Lambda, ECS, EKS, Fargate", "Functions, AKS", "GKE, Knative"),
    ("API / Integration", "API Gateway, EventBridge, Step Functions", "Functions, Service Bus", "Pub/Sub"),
    ("Data / Search", "S3, DynamoDB, RDS/Aurora, OpenSearch", "Cosmos DB", "BigQuery"),
    ("Observability", "CloudWatch", "App Insights", "Cloud Logging / Metrics"),
    ("Security", "IAM", "Key Vault, Entra/RBAC", "IAM, Secret Manager"),
]


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend(
            [
                "C:/Windows/Fonts/segoeuib.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
            ]
        )
    else:
        candidates.extend(
            [
                "C:/Windows/Fonts/segoeui.ttf",
                "C:/Windows/Fonts/arial.ttf",
            ]
        )

    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


TITLE_FONT = load_font(42, bold=True)
SUBTITLE_FONT = load_font(22)
SECTION_FONT = load_font(24, bold=True)
BODY_FONT = load_font(18)
SMALL_FONT = load_font(16)


def draw_gradient_background(image: Image.Image) -> None:
    draw = ImageDraw.Draw(image)
    top = (245, 248, 252)
    bottom = (228, 236, 247)
    for y in range(HEIGHT):
        ratio = y / max(HEIGHT - 1, 1)
        color = tuple(int(top[index] + (bottom[index] - top[index]) * ratio) for index in range(3))
        draw.line((0, y, WIDTH, y), fill=color)

    draw.ellipse((1900, -120, 2860, 840), fill=(212, 227, 245))
    draw.ellipse((-220, 1520, 880, 2520), fill=(221, 233, 243))


def rounded_box(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], fill: tuple[int, int, int], outline: tuple[int, int, int], radius: int = 26, width: int = 2) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_paragraph(draw: ImageDraw.ImageDraw, text: str, xy: tuple[int, int], font: ImageFont.ImageFont, max_width: int, fill: tuple[int, int, int], line_gap: int = 6) -> int:
    x, y = xy
    lines = wrap_text(draw, text, font, max_width)
    line_height = font.size + line_gap if hasattr(font, "size") else 22
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def draw_labeled_box(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], title: str, body: str, fill: tuple[int, int, int], outline: tuple[int, int, int], body_font: ImageFont.ImageFont = BODY_FONT) -> None:
    rounded_box(draw, xy, fill, outline)
    x1, y1, x2, y2 = xy
    draw.text((x1 + 18, y1 + 14), title, font=SECTION_FONT, fill=(24, 39, 68))
    draw_paragraph(draw, body, (x1 + 18, y1 + 54), body_font, x2 - x1 - 36, (52, 66, 91))


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], fill: tuple[int, int, int] = (72, 102, 138), width: int = 4) -> None:
    draw.line((start, end), fill=fill, width=width)
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    if dx == 0 and dy == 0:
        return
    if abs(dx) >= abs(dy):
        direction = 1 if dx >= 0 else -1
        tip = end
        left = (tip[0] - 18 * direction, tip[1] - 10)
        right = (tip[0] - 18 * direction, tip[1] + 10)
    else:
        direction = 1 if dy >= 0 else -1
        tip = end
        left = (tip[0] - 10, tip[1] - 18 * direction)
        right = (tip[0] + 10, tip[1] - 18 * direction)
    draw.polygon([tip, left, right], fill=fill)


def draw_multicloud_table(draw: ImageDraw.ImageDraw) -> None:
    panel = (2170, 130, 2740, 1390)
    rounded_box(draw, panel, (242, 247, 253), (139, 165, 195), radius=30, width=3)
    draw.text((2195, 155), "MultiCloud Deployment Map", font=TITLE_FONT, fill=(17, 40, 77))
    draw_paragraph(
        draw,
        "Explicit service mapping for a MultiCloud application discussion across AWS, Azure, and GCP.",
        (2195, 215),
        SUBTITLE_FONT,
        500,
        (69, 86, 110),
    )

    table_x = 2190
    table_y = 310
    col_widths = [110, 130, 150, 150]
    headers = ["Domain", "AWS", "Azure", "GCP"]
    row_height = 148

    current_x = table_x
    for index, header in enumerate(headers):
        x2 = current_x + col_widths[index]
        rounded_box(draw, (current_x, table_y, x2, table_y + 52), (30, 92, 146), (30, 92, 146), radius=12, width=1)
        draw.text((current_x + 12, table_y + 12), header, font=SECTION_FONT, fill=(255, 255, 255))
        current_x = x2 + 8

    y = table_y + 68
    for row_index, row in enumerate(MULTICLOUD_ROWS):
        current_x = table_x
        tone = (248, 251, 255) if row_index % 2 == 0 else (238, 245, 252)
        for col_index, cell in enumerate(row):
            x2 = current_x + col_widths[col_index]
            rounded_box(draw, (current_x, y, x2, y + row_height), tone, (172, 193, 215), radius=12, width=2)
            cell_font = SMALL_FONT if col_index else BODY_FONT
            draw_paragraph(draw, cell, (current_x + 10, y + 10), cell_font, col_widths[col_index] - 20, (44, 60, 84), line_gap=4)
            current_x = x2 + 8
        y += row_height + 8


def draw_capability_grid(draw: ImageDraw.ImageDraw) -> None:
    draw.text((350, 1440), "Platform & Delivery Capabilities", font=TITLE_FONT, fill=(20, 45, 82))
    draw_paragraph(
        draw,
        "Complete terminology coverage grouped for readability so the discussion can move from core agent flow to platform breadth without losing the MultiCloud story.",
        (350, 1495),
        SUBTITLE_FONT,
        1740,
        (67, 84, 108),
    )

    grid_x = 350
    grid_y = 1565
    box_width = 585
    box_height = 145
    x_gap = 22
    y_gap = 22
    fills = [(248, 251, 255), (241, 247, 253), (246, 249, 252)]

    for index, (title, body) in enumerate(TERMINOLOGY_GROUPS):
        row = index // 3
        col = index % 3
        x1 = grid_x + col * (box_width + x_gap)
        y1 = grid_y + row * (box_height + y_gap)
        xy = (x1, y1, x1 + box_width, y1 + box_height)
        draw_labeled_box(draw, xy, title, body, fills[index % len(fills)], (160, 186, 213), body_font=SMALL_FONT)


def build_diagram() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw_gradient_background(image)

    draw.text((340, 48), "Agentic AI Architecture for MultiCloud Applications", font=TITLE_FONT, fill=(17, 40, 77))
    draw.text((340, 100), "Updated to include the complete terminology toolset, cloud mappings, platform delivery stack, and governance controls.", font=SUBTITLE_FONT, fill=(69, 86, 110))

    rounded_box(draw, (36, 132, 300, 1390), (235, 242, 250), (137, 164, 196), radius=28, width=3)
    draw.text((60, 165), "Observability &", font=SECTION_FONT, fill=(21, 46, 84))
    draw.text((60, 194), "Governance Rail", font=SECTION_FONT, fill=(21, 46, 84))
    left_sections = [
        ("Eval + Trace", "LangSmith, trajectory evals, golden-set regression, audit IDs, drift monitoring, cost and latency tracking."),
        ("DevSecOps", "GitHub Actions, GitLab CI, Jenkins, ArgoCD, trunk-based development, Twelve-Factor App discipline."),
        ("Security", "Threat modeling, OWASP Top 10, SAST, DAST, dependency and secret scanning, RBAC, encryption at rest/in transit."),
        ("Compliance", "Prompt-injection mitigation, model governance, HIPAA, GDPR, FDA 21 CFR Part 11, SOC 2."),
    ]
    left_y = 260
    for title, body in left_sections:
        draw_labeled_box(draw, (56, left_y, 280, left_y + 220), title, body, (248, 251, 255), (169, 192, 214), body_font=SMALL_FONT)
        left_y += 245

    draw_labeled_box(
        draw,
        (350, 140, 790, 275),
        "Input Stage",
        "User query, enterprise context, session roles, tenant boundary, schema validation, and PII/prompt-injection scrub before orchestration starts.",
        (248, 250, 254),
        (144, 169, 197),
    )
    draw_labeled_box(
        draw,
        (830, 140, 1270, 275),
        "Planner",
        "ReAct decomposition, query rewriting, retriever selection, planner/executor pattern, tool budget, and pathing decisions for MultiCloud workflows.",
        (240, 247, 253),
        (144, 169, 197),
    )
    draw_labeled_box(
        draw,
        (1310, 140, 1750, 275),
        "Executor LLM",
        "Function-calling and structured output using Anthropic Claude, OpenAI/Azure OpenAI, Bedrock-hosted models, Llama, and Mistral with model routing.",
        (248, 250, 254),
        (144, 169, 197),
    )

    arrow(draw, (790, 208), (830, 208))
    arrow(draw, (1270, 208), (1310, 208))

    rounded_box(draw, (350, 320, 1750, 860), (238, 245, 252), (118, 147, 181), radius=34, width=3)
    draw.text((380, 348), "Agent Orchestrator", font=TITLE_FONT, fill=(20, 45, 82))
    draw.text((380, 400), "Coordinates reasoning, memory, tool-use, retrieval, and safe handoff between application services and cloud platforms.", font=SUBTITLE_FONT, fill=(70, 88, 112))

    draw_labeled_box(
        draw,
        (390, 455, 825, 650),
        "Memory",
        "Short-term plan state, tool observations, user preferences, tenant context, and episode summaries stored in vector and graph-aware memory layers.",
        (248, 251, 255),
        (160, 186, 213),
    )
    draw_labeled_box(
        draw,
        (855, 455, 1290, 650),
        "Guardrails",
        "Grounding checks, citation verification, PII redaction, policy filters, JSON schema enforcement, and human-in-the-loop escalation.",
        (248, 251, 255),
        (160, 186, 213),
    )
    draw_labeled_box(
        draw,
        (1320, 455, 1710, 650),
        "Agent Frameworks",
        "AutoGen, LangGraph, CrewAI, MCP servers, AI pair-programming hooks, eval harnesses, and reusable orchestrator policies.",
        (248, 251, 255),
        (160, 186, 213),
    )
    draw_labeled_box(
        draw,
        (390, 690, 1710, 820),
        "Application Patterns",
        "Microservices, serverless, event-driven design, DDD, hexagonal architecture, CQRS, Saga, API-first design, and embedded delivery patterns for adoption.",
        (248, 251, 255),
        (160, 186, 213),
        body_font=SMALL_FONT,
    )

    draw.text((350, 905), "Tool Layer", font=TITLE_FONT, fill=(20, 45, 82))
    tool_boxes = [
        ("Retriever Mesh", "Agentic RAG, embeddings, ANN + hybrid search, Pinecone, pgvector, Weaviate, OpenSearch, reranking and retrieval orchestration."),
        ("Graph + Data Tools", "Neo4j, Cypher, GDS, Causal Cluster, GraphQL, PostgreSQL, MySQL, MongoDB, Snowflake, BigQuery."),
        ("Execution + Integration", "REST, GraphQL, gRPC, WebSockets, internal APIs, 3rd-party APIs, Kafka, Airflow, Step Functions, Service Bus, Pub/Sub."),
        ("Engineering Tooling", "Cursor, Claude Code, GitHub Copilot, AI code review, AI test generation, secure SDLC automation, and platform diagnostics."),
    ]
    tool_x = 350
    for title, body in tool_boxes:
        draw_labeled_box(draw, (tool_x, 960, tool_x + 330, 1245), title, body, (248, 251, 255), (160, 186, 213), body_font=SMALL_FONT)
        tool_x += 350

    draw.text((350, 1280), "Knowledge & Runtime Substrate", font=TITLE_FONT, fill=(20, 45, 82))
    substrate_boxes = [
        ("Data Foundation", "S3/object lake, DynamoDB, RDS/Aurora, Cosmos DB, PostgreSQL, MySQL, MongoDB, Snowflake, Databricks."),
        ("Compute Foundation", "Lambda, ECS, EKS, Fargate, AKS, Azure Functions, GKE, Docker, Helm, Istio, Knative."),
        ("Platform Engineering", "Terraform, AWS CDK, CloudFormation, Bicep, Kubernetes portability, trunk-based delivery, rapid onboarding and technical adoption playbooks."),
    ]
    substrate_x = 350
    for title, body in substrate_boxes:
        draw_labeled_box(draw, (substrate_x, 1330, substrate_x + 446, 1420), title, body, (241, 247, 253), (160, 186, 213), body_font=SMALL_FONT)
        substrate_x += 468

    draw_labeled_box(
        draw,
        (1820, 140, 2120, 380),
        "Output Stage",
        "Grounded response with citations, audit ID, structured JSON or narrative answer, plus deployment-specific recommendations for AWS, Azure, and GCP.",
        (247, 250, 254),
        (144, 169, 197),
    )
    draw_labeled_box(
        draw,
        (1820, 420, 2120, 720),
        "Discussion Framing",
        "Use the diagram in three passes: core agent runtime, platform/tooling breadth, then cloud-specific deployment tradeoffs and compliance posture.",
        (247, 250, 254),
        (144, 169, 197),
    )
    draw_labeled_box(
        draw,
        (1820, 760, 2120, 1040),
        "Legend",
        "Blue boxes = architecture flow. Pale cards = supporting capability stacks. Right panel = cloud-specific equivalents for MultiCloud conversations.",
        (247, 250, 254),
        (144, 169, 197),
    )

    arrow(draw, (1750, 208), (1820, 208))
    arrow(draw, (1045, 275), (1045, 320))
    arrow(draw, (1045, 860), (1045, 930))
    arrow(draw, (1045, 1245), (1045, 1280))

    draw_multicloud_table(draw)
    draw_capability_grid(draw)
    return image


def main() -> None:
    image = build_diagram()
    for output_path in OUTPUT_PATHS:
        image.save(output_path, format="JPEG", quality=92)
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()