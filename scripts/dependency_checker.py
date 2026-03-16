#!/usr/bin/env python3
import argparse
import sys
from datetime import UTC, datetime, timedelta, timezone

import requests
import tomli
import tomlkit
import tomlkit.exceptions
from packaging.requirements import Requirement
from packaging.version import InvalidVersion, Version
from rich.console import Console
from rich.markup import escape
from rich.theme import Theme
from tomlkit.items import Array

# --- Configuration ---
# To install script dependencies:
# uv pip install "rich" "requests" "packaging" "tomli" "tomlkit"
#
# Example commands for managing project dependencies with uv:
# uv add --optional dev --bounds major rich requests packaging tomli tomlkit
# uv sync --all-extras
PYPROJECT_PATH = "pyproject.toml"
DAYS_OLD_THRESHOLD = 3

# --- Setup Rich Console for Colored Output ---
custom_theme = Theme(
    {
        "info": "gray50",
        "success": "green",
        "warning": "orange1",
        "primary": "purple",
        "error": "bold red",
        "locked": "dim cyan",  # Locked dependencies - dimmer than grey
    }
)
console = Console(theme=custom_theme)

# --- Caching and Session for Performance ---
pypi_cache = {}
session = requests.Session()


def get_package_data(package_name: str) -> dict | None:
    if package_name in pypi_cache:
        return pypi_cache[package_name]
    try:
        response = session.get(f"https://pypi.org/pypi/{package_name}/json")
        response.raise_for_status()
        data = response.json()
        pypi_cache[package_name] = data
        return data
    except requests.RequestException as e:
        console.print(f"Error fetching {package_name}: {e}", style="error")
        return None


def find_latest_versions(package_data: dict) -> tuple[tuple | None, tuple | None]:
    now = datetime.now(UTC)
    threshold_date = now - timedelta(days=DAYS_OLD_THRESHOLD)
    latest_stable_info, latest_stable_past_threshold_info = None, None
    releases = package_data.get("releases", {})
    for version_str, release_files in releases.items():
        try:
            version = Version(version_str)
            if version.is_prerelease or not release_files:
                continue
            upload_time = datetime.fromisoformat(release_files[0].get("upload_time_iso_8601"))
            if latest_stable_info is None or version > latest_stable_info[0]:
                latest_stable_info = (version, upload_time)
            if upload_time < threshold_date:
                if (
                    latest_stable_past_threshold_info is None
                    or version > latest_stable_past_threshold_info[0]
                ):
                    latest_stable_past_threshold_info = (version, upload_time)
        except (InvalidVersion, TypeError):
            continue
    return latest_stable_info, latest_stable_past_threshold_info


def generate_new_specifier(req: Requirement, new_version: Version) -> str:
    extras = f"[{','.join(sorted(req.extras))}]" if req.extras else ""
    upper_bound = (
        f"<{new_version.major + 1}.0.0"
        if new_version.major >= 1
        else f"<0.{new_version.minor + 1}.0"
    )
    return f"{req.name}{extras}>={new_version},{upper_bound}"


def format_age_and_date(upload_time: datetime) -> tuple[str, str]:
    delta = datetime.now(UTC) - upload_time
    days_ago = delta.days
    age_str = f"{days_ago} day{'s' if days_ago != 1 else ''} ago"
    date_str = upload_time.strftime("%m-%d-%y")
    return age_str, date_str


def check_dependencies(args: argparse.Namespace) -> list:
    try:
        with open(PYPROJECT_PATH, encoding="utf-8") as f:
            pyproject_doc = tomlkit.load(f)
        with open(PYPROJECT_PATH, "rb") as f:
            pyproject_data = tomli.load(f)
    except FileNotFoundError:
        console.print(f"Error: {PYPROJECT_PATH} not found.", style="error")
        sys.exit(1)
    except (tomli.TOMLDecodeError, tomlkit.exceptions.TOMLKitError) as e:
        console.print(f"Error: Could not parse {PYPROJECT_PATH}. {e}", style="error")
        sys.exit(1)

    changes_to_apply = []

    dependency_groups = {}
    if "project" in pyproject_data:
        if "dependencies" in pyproject_data["project"]:
            dependency_groups[("project", "dependencies")] = pyproject_data["project"][
                "dependencies"
            ]
        if "optional-dependencies" in pyproject_data["project"]:
            for group, deps in pyproject_data["project"]["optional-dependencies"].items():
                dependency_groups[("project", "optional-dependencies", group)] = deps

    for group_keys, dependencies in dependency_groups.items():
        group_name = ".".join(group_keys)
        output_lines_for_group = []

        # Get the tomlkit section to access comments
        tomlkit_section = pyproject_doc
        for key in group_keys:
            tomlkit_section = tomlkit_section.get(key)  # type: ignore
            if tomlkit_section is None:
                break

        for idx, dep_string in enumerate(dependencies):
            # Check if this dependency has a "lock" comment
            is_locked = False
            if isinstance(tomlkit_section, Array) and hasattr(tomlkit_section, "_value"):
                # Access internal _value list which contains tuples of (whitespace, value, comma, comment)
                if idx < len(tomlkit_section._value):
                    item_tuple = tomlkit_section._value[idx]
                    # Check if tuple has a Comment object (inline comments)
                    for element in item_tuple:
                        if (
                            hasattr(element, "__class__")
                            and "Comment" in element.__class__.__name__
                        ):
                            comment_text = str(element).strip()
                            if "lock" in comment_text.lower():
                                is_locked = True
                                break
            # Handle locked dependencies
            if is_locked:
                output_lines_for_group.append(
                    f"[locked]{dep_string:<60} (Locked - skipped)[/locked]"
                )
                continue

            try:
                req = Requirement(dep_string)
            except Exception:
                if args.all:
                    output_lines_for_group.append(
                        f"[info]{dep_string:<60} (Could not parse)[/info]"
                    )
                continue

            data = get_package_data(req.name)
            if not data:
                continue

            latest_stable_info, latest_stable_past_threshold_info = find_latest_versions(data)
            if not latest_stable_info:
                if args.all:
                    output_lines_for_group.append(
                        f"[info]{dep_string:<60} (No stable versions found)[/info]"
                    )
                continue

            latest_stable, latest_stable_time = latest_stable_info
            age_str, date_str = format_age_and_date(latest_stable_time)
            current_spec_satisfied = latest_stable in req.specifier

            if current_spec_satisfied:
                if args.all:
                    msg = f"(Up to date at {latest_stable}, released {age_str} on {date_str})"
                    output_lines_for_group.append(f"[info]{dep_string:<60} {msg}[/info]")
            else:
                is_too_new = latest_stable_time > (
                    datetime.now(UTC) - timedelta(days=DAYS_OLD_THRESHOLD)
                )
                if is_too_new:
                    msg = f"Newest is {latest_stable} (released {age_str}, but is too new)"
                    output_lines_for_group.append(f"[warning]{dep_string:<60} {msg}[/warning]")
                    if latest_stable_past_threshold_info:
                        older_ver, older_time = latest_stable_past_threshold_info
                        if older_ver not in req.specifier:
                            older_age_str, _ = format_age_and_date(older_time)
                            new_spec = generate_new_specifier(req, older_ver)
                            changes_to_apply.append((group_keys, dep_string, new_spec))
                            output_lines_for_group.append(
                                f"[primary]  └─ Safe update available: {older_ver} (released {older_age_str}) ({new_spec})[/primary]"
                            )
                else:
                    new_spec = generate_new_specifier(req, latest_stable)
                    changes_to_apply.append((group_keys, dep_string, new_spec))
                    msg = f"Can be updated to {latest_stable} (released {age_str})"
                    output_lines_for_group.append(
                        f"[success]{dep_string:<60} {msg} ({new_spec})[/success]"
                    )

        if output_lines_for_group:
            header = f"--- [{group_name}] ---"
            console.print(f"\n{escape(header)}", style="bold")
            for line in output_lines_for_group:
                console.print(line)

    return changes_to_apply


def apply_changes(changes: list):
    """Reads, modifies, and writes the pyproject.toml file using tomlkit."""
    if not changes:
        console.print("\nNo safe updates to apply.", style="info")
        return

    console.print(
        f"\n[bold yellow]Applying {len(changes)} safe update(s) to {PYPROJECT_PATH}...[/bold yellow]"
    )
    with open(PYPROJECT_PATH, encoding="utf-8") as f:
        doc = tomlkit.load(f)

    for group_keys, old_dep, new_dep in changes:
        # Navigate to the correct section (e.g., doc['project']['dependencies'])
        section = doc
        for key in group_keys:
            section = section[key]  # type: ignore

        # --- PYRIGHT FIX STARTS HERE ---
        # This check confirms to the type checker that 'section' is a list-like Array
        if not isinstance(section, Array):
            console.print(
                f"[error]Could not apply change: section '{'.'.join(group_keys)}' is not a list.[/error]"
            )
            continue
        # --- PYRIGHT FIX ENDS HERE ---

        # Now all operations below are known to be safe
        for i, item in enumerate(section):
            if str(item) == old_dep:
                section[i] = new_dep
                break

    with open(PYPROJECT_PATH, "w", encoding="utf-8") as f:
        tomlkit.dump(doc, f)

    console.print("✅ [bold green]pyproject.toml has been updated successfully.[/bold green]")


def main():
    parser = argparse.ArgumentParser(
        description="Check for updates to dependencies in pyproject.toml."
    )
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Show all dependencies, including those that are up to date.",
    )
    parser.add_argument(
        "--apply-changes",
        action="store_true",
        help="Automatically modify pyproject.toml with all safe updates (green and purple items).",
    )
    args = parser.parse_args()

    changes = check_dependencies(args)

    if args.apply_changes:
        apply_changes(changes)


if __name__ == "__main__":
    main()
