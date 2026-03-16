#!/usr/bin/env python3
"""
Installation script for the MCP Code Context server

This script installs the MCP Code Context server in Claude or other MCP-compatible
environments. It handles the installation of dependencies and configuration.
"""

import argparse
import os
import subprocess
import sys


def parse_args():
    parser = argparse.ArgumentParser(description="Install the MCP Code Context server")
    parser.add_argument(
        "--name",
        default="CodeContext",
        help="Name for the MCP server (default: CodeContext)",
    )
    parser.add_argument(
        "--env-file",
        help="Path to .env file for environment variables",
        default=None,
    )
    parser.add_argument(
        "--mcp-path",
        required=True,
        help="Path to the MCP server file",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Build the installation command
    cmd = ["mcp", "install", args.mcp_path]

    # Add dependencies
    cmd.extend(
        [
            "--with",
            "puremagic>=1.28.0,<2.0.0",
            "--with",
            "diskcache>=5.4.0,<6.0.0",
            "--with",
            "mcp>=1.4.1,<2.0.0",
        ]
    )

    # Add optional dependencies
    cmd.extend(["--with", "tiktoken>=0.9.0,<1.0.0"])  # For token counting

    # Add name if provided
    if args.name:
        cmd.extend(["--name", args.name])

    # Add env-file if provided
    if args.env_file:
        cmd.extend(["--env-file", args.env_file])

    # Print the command
    print("Running installation command:")
    print(" ".join(cmd))

    # Execute the command
    try:
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        print("\nInstallation successful!")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"\nInstallation failed with error code {e.returncode}:")
        print(e.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
