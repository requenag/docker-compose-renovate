#!/usr/bin/env python3
"""Generate a catalogue of Docker Compose products in this repository."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - depends on the local environment
    yaml = None


COMPOSE_FILENAMES = {
    "compose.yaml",
    "compose.yml",
    "docker-compose.yaml",
    "docker-compose.yml",
}

DIRECT_SERVICE_KEYS = {
    "build",
    "container_name",
    "depends_on",
    "image",
    "networks",
    "ports",
    "profiles",
    "restart",
}

KEY_RE = re.compile(r"^(?P<indent>\s*)(?P<key>[A-Za-z0-9_.-]+)\s*:\s*(?P<value>.*)$")


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]

    parser = argparse.ArgumentParser(
        description="Generate a Markdown or JSON catalogue of Docker Compose products.",
    )
    parser.add_argument(
        "--compose-root",
        type=Path,
        default=repo_root / "docker-compose",
        help="Directory containing the product compose folders.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=repo_root / "docker-compose-catalogue.md",
        help="Output file path. Defaults to docker-compose-catalogue.md in the repo root.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default=None,
        help="Output format. Defaults to JSON for .json outputs, otherwise Markdown.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print the catalogue instead of writing it to --output.",
    )
    parser.add_argument(
        "--fail-on-parse-error",
        action="store_true",
        help="Exit with an error if any compose file cannot be parsed as YAML.",
    )

    return parser.parse_args()


def find_compose_files(compose_root: Path) -> list[Path]:
    return sorted(
        path
        for path in compose_root.rglob("*")
        if path.is_file() and path.name in COMPOSE_FILENAMES
    )


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def strip_inline_comment(value: str) -> str:
    quote: str | None = None
    escaped = False

    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char in {"'", '"'}:
            if quote == char:
                quote = None
            elif quote is None:
                quote = char
            continue
        if char == "#" and quote is None:
            return value[:index].rstrip()

    return value.strip()


def clean_scalar(value: Any) -> str:
    if value is None:
        return ""

    text = strip_inline_comment(str(value).strip())
    if text in {"", "|", ">"}:
        return ""

    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]

    return text


def ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        return list(value)
    return [value]


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        clean_value = clean_scalar(value)
        if clean_value and clean_value not in seen:
            seen.add(clean_value)
            result.append(clean_value)

    return result


def relative_path(path: Path, start: Path) -> str:
    try:
        return path.relative_to(start).as_posix()
    except ValueError:
        return path.as_posix()


def product_name(compose_file: Path, compose_root: Path) -> str:
    parent = compose_file.parent
    try:
        return parent.relative_to(compose_root).as_posix()
    except ValueError:
        return parent.name


def normalize_ports(ports: Any) -> list[str]:
    normalized: list[str] = []

    for port in ensure_list(ports):
        if isinstance(port, dict):
            published = clean_scalar(port.get("published") or port.get("host_ip") or "")
            target = clean_scalar(port.get("target") or "")
            protocol = clean_scalar(port.get("protocol") or "")
            mode = clean_scalar(port.get("mode") or "")
            parts = []
            if published and target:
                parts.append(f"{published}:{target}")
            elif target:
                parts.append(target)
            if protocol:
                parts.append(protocol)
            if mode:
                parts.append(mode)
            normalized.append("/".join(parts) if parts else json.dumps(port, sort_keys=True))
        else:
            normalized.append(clean_scalar(port))

    return unique(normalized)


def normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, dict):
        return unique([str(key) for key in value])
    return unique([clean_scalar(item) for item in ensure_list(value)])


def normalize_build(build: Any) -> str:
    if isinstance(build, dict):
        context = clean_scalar(build.get("context") or "")
        dockerfile = clean_scalar(build.get("dockerfile") or "")
        if context and dockerfile:
            return f"{context} ({dockerfile})"
        return context or dockerfile or json.dumps(build, sort_keys=True)

    return clean_scalar(build)


def service_from_mapping(name: str, service: Any) -> dict[str, Any]:
    if not isinstance(service, dict):
        return {
            "name": name,
            "container_name": "",
            "image": "",
            "build": "",
            "ports": [],
            "depends_on": [],
            "profiles": [],
            "networks": [],
            "restart": "",
        }

    return {
        "name": name,
        "container_name": clean_scalar(service.get("container_name") or ""),
        "image": clean_scalar(service.get("image") or ""),
        "build": normalize_build(service.get("build")),
        "ports": normalize_ports(service.get("ports")),
        "depends_on": normalize_string_list(service.get("depends_on")),
        "profiles": normalize_string_list(service.get("profiles")),
        "networks": normalize_string_list(service.get("networks")),
        "restart": clean_scalar(service.get("restart") or ""),
    }


def parse_with_yaml(text: str) -> tuple[list[dict[str, Any]], str | None]:
    if yaml is None:
        return [], "PyYAML is not installed"

    try:
        loaded = yaml.safe_load(text)
    except Exception as exc:  # pragma: no cover - depends on repository data
        return [], str(exc)

    if not isinstance(loaded, dict):
        return [], "compose file did not contain a YAML mapping"

    services = loaded.get("services", {})
    if not isinstance(services, dict):
        return [], "compose file did not contain a services mapping"

    return [service_from_mapping(str(name), value) for name, value in services.items()], None


def line_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def is_ignored_line(line: str) -> bool:
    stripped = line.strip()
    return not stripped or stripped.startswith("#") or stripped.startswith("{%") or stripped.startswith("{{")


def parse_inline_list(value: str) -> list[str] | None:
    value = clean_scalar(value)
    if not (value.startswith("[") and value.endswith("]")):
        return None

    content = value[1:-1].strip()
    if not content:
        return []

    return unique(item.strip().strip("'\"") for item in content.split(","))


def collect_nested_values(
    block: list[str],
    start_index: int,
    key_indent: int,
    stop_indent: int,
) -> list[str]:
    values: list[str] = []

    for line in block[start_index + 1 :]:
        if is_ignored_line(line):
            continue

        indent = line_indent(line)
        if indent <= stop_indent:
            break
        if indent <= key_indent and KEY_RE.match(line):
            break

        stripped = line.strip()
        if stripped.startswith("- "):
            item = clean_scalar(stripped[2:])
            if item:
                values.append(item)
            continue

        match = KEY_RE.match(line)
        if match and indent == key_indent + 2:
            values.append(clean_scalar(match.group("key")))

    return unique(values)


def parse_service_block(name: str, block: list[str], service_indent: int) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "name": name,
        "container_name": "",
        "image": "",
        "build": "",
        "ports": [],
        "depends_on": [],
        "profiles": [],
        "networks": [],
        "restart": "",
    }

    for index, line in enumerate(block):
        if is_ignored_line(line):
            continue

        match = KEY_RE.match(line)
        if not match:
            continue

        indent = len(match.group("indent"))
        if indent <= service_indent:
            continue

        key = match.group("key")
        if key not in DIRECT_SERVICE_KEYS:
            continue

        value = clean_scalar(match.group("value"))
        inline_values = parse_inline_list(value)

        if key in {"ports", "depends_on", "profiles", "networks"}:
            fields[key] = inline_values if inline_values is not None else collect_nested_values(
                block,
                index,
                indent,
                service_indent,
            )
        elif key == "build":
            fields[key] = value or ", ".join(collect_nested_values(block, index, indent, service_indent))
        else:
            fields[key] = value

    fields["ports"] = normalize_ports(fields["ports"])
    fields["depends_on"] = normalize_string_list(fields["depends_on"])
    fields["profiles"] = normalize_string_list(fields["profiles"])
    fields["networks"] = normalize_string_list(fields["networks"])
    fields["build"] = clean_scalar(fields["build"])

    return fields


def parse_with_text_fallback(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    service_start = None
    service_root_indent = 0

    for index, line in enumerate(lines):
        match = KEY_RE.match(line)
        if match and match.group("key") == "services":
            service_start = index + 1
            service_root_indent = len(match.group("indent"))
            break

    if service_start is None:
        return []

    service_indent: int | None = None
    services: list[dict[str, Any]] = []
    current_name: str | None = None
    current_block: list[str] = []

    for line in lines[service_start:]:
        if is_ignored_line(line):
            if current_name is not None:
                current_block.append(line)
            continue

        indent = line_indent(line)
        match = KEY_RE.match(line)

        if match and indent <= service_root_indent:
            break

        if service_indent is None and match and indent > service_root_indent:
            service_indent = indent

        if service_indent is not None and match and indent == service_indent:
            if current_name is not None:
                services.append(parse_service_block(current_name, current_block, service_indent))
            current_name = match.group("key")
            current_block = []
            continue

        if current_name is not None:
            current_block.append(line)

    if current_name is not None:
        services.append(parse_service_block(current_name, current_block, service_indent or service_root_indent))

    return services


def scan_images_from_text(text: str) -> list[str]:
    images: list[str] = []

    for line in text.splitlines():
        if is_ignored_line(line):
            continue
        match = KEY_RE.match(line)
        if match and match.group("key") == "image":
            image = clean_scalar(match.group("value"))
            if image:
                images.append(image)

    return unique(images)


def parse_compose_file(compose_file: Path, compose_root: Path, repo_root: Path) -> dict[str, Any]:
    text = read_text(compose_file)
    yaml_services, parse_error = parse_with_yaml(text)
    text_services = parse_with_text_fallback(text)
    services = yaml_services or text_services
    text_images = scan_images_from_text(text)
    service_images = unique([service["image"] for service in services])
    images = unique([*service_images, *text_images])

    ports = unique(
        port
        for service in services
        for port in service.get("ports", [])
    )

    return {
        "product": product_name(compose_file, compose_root),
        "compose_file": relative_path(compose_file, repo_root),
        "services": services,
        "service_count": len(services),
        "images": images,
        "image_count": len(images),
        "ports": ports,
        "port_count": len(ports),
        "parser": "yaml" if yaml_services else "text",
        "parse_error": parse_error if not yaml_services else "",
    }


def build_catalogue(compose_root: Path) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    compose_root = compose_root.resolve()
    compose_files = find_compose_files(compose_root)
    products = [parse_compose_file(path, compose_root, repo_root) for path in compose_files]

    return {
        "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        "compose_root": relative_path(compose_root, repo_root),
        "product_count": len(products),
        "service_count": sum(product["service_count"] for product in products),
        "image_count": len(unique(image for product in products for image in product["images"])),
        "products": products,
    }


def md_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def code(value: str) -> str:
    return f"`{md_escape(value)}`"


def summarize(values: list[str], limit: int = 4) -> str:
    clean_values = unique(values)
    if not clean_values:
        return "-"

    displayed = ", ".join(code(value) for value in clean_values[:limit])
    remaining = len(clean_values) - limit
    if remaining > 0:
        displayed += f", +{remaining} more"
    return displayed


def service_summary(service: dict[str, Any]) -> str:
    parts = [code(service["name"])]

    if service.get("container_name"):
        parts.append(f"container {code(service['container_name'])}")
    if service.get("image"):
        parts.append(f"image {code(service['image'])}")
    elif service.get("build"):
        parts.append(f"build {code(service['build'])}")
    if service.get("ports"):
        parts.append(f"ports {summarize(service['ports'], limit=6)}")
    if service.get("depends_on"):
        parts.append(f"depends on {summarize(service['depends_on'], limit=6)}")
    if service.get("profiles"):
        parts.append(f"profiles {summarize(service['profiles'], limit=6)}")
    if service.get("restart"):
        parts.append(f"restart {code(service['restart'])}")

    return "; ".join(parts)


def render_markdown(catalogue: dict[str, Any]) -> str:
    lines = [
        "# Docker Compose Product Catalogue",
        "",
        f"Generated: `{catalogue['generated_at']}`",
        f"Compose root: `{catalogue['compose_root']}`",
        "",
        f"- Products: {catalogue['product_count']}",
        f"- Services: {catalogue['service_count']}",
        f"- Unique images: {catalogue['image_count']}",
        "",
        "## Products",
        "",
        "| Product | Compose file | Services | Images | Ports |",
        "| --- | --- | ---: | --- | --- |",
    ]

    for product in catalogue["products"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    md_escape(product["product"]),
                    code(product["compose_file"]),
                    str(product["service_count"]),
                    summarize(product["images"]),
                    summarize(product["ports"]),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Service Details", ""])

    for product in catalogue["products"]:
        lines.extend(
            [
                f"### {product['product']}",
                "",
                f"- Compose file: {code(product['compose_file'])}",
                f"- Services: {product['service_count']}",
                f"- Images: {summarize(product['images'], limit=12)}",
            ]
        )
        if product.get("parse_error"):
            lines.append(f"- Parser note: {md_escape(product['parse_error'])}")
        lines.append("")

        if product["services"]:
            for service in product["services"]:
                lines.append(f"- {service_summary(service)}")
        else:
            lines.append("- No services detected.")

        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_catalogue(catalogue: dict[str, Any], output_format: str) -> str:
    if output_format == "json":
        return json.dumps(catalogue, indent=2, sort_keys=True) + "\n"
    return render_markdown(catalogue)


def main() -> int:
    args = parse_args()
    output_format = args.format
    if output_format is None:
        output_format = "json" if args.output.suffix.lower() == ".json" else "markdown"

    compose_root = args.compose_root
    if not compose_root.exists():
        print(f"Compose root not found: {compose_root}", file=sys.stderr)
        return 1

    catalogue = build_catalogue(compose_root)
    parse_errors = [product for product in catalogue["products"] if product.get("parse_error")]
    if args.fail_on_parse_error and parse_errors:
        print("One or more compose files could not be parsed as YAML:", file=sys.stderr)
        for product in parse_errors:
            print(f"- {product['compose_file']}: {product['parse_error']}", file=sys.stderr)
        return 1

    content = render_catalogue(catalogue, output_format)

    if args.stdout:
        print(content, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
        print(
            f"Wrote {catalogue['product_count']} products and "
            f"{catalogue['service_count']} services to {args.output}",
        )

    if yaml is None:
        print(
            "PyYAML is not installed; used the built-in text parser. "
            "Install PyYAML for fuller Compose merge/anchor handling.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
