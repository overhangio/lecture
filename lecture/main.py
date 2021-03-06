#! /usr/bin/env python
import argparse
import importlib
import logging
import os
import sys

from lecture.exceptions import LectureError

logger = logging.getLogger(__name__)


def main() -> None:
    try:
        run()
    except LectureError as e:
        logger.error(e.args[0])
        sys.exit(1)


def run() -> None:
    args = parse_args()

    load_module = f"lecture.formats.{args.from_format}.reader"
    load_func = importlib.import_module(load_module).load
    dump_module = f"lecture.formats.{args.to_format}.writer"
    dump_func = importlib.import_module(dump_module).dump

    course = load_func(args.input)
    dump_func(course, args.output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert online courses from one format to another."
    )
    parser.add_argument(
        "-f", "--from-format", choices=["html", "md", "olx"], default=None
    )
    parser.add_argument(
        "-t", "--to-format", choices=["html", "md", "olx"], default=None
    )
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("input", help="Input file or directory.")
    parser.add_argument("output", help="Output file or directory.")
    args = parser.parse_args()

    # Configure logging
    log_level: int = logging.WARNING
    if args.verbose == 1:
        log_level = logging.INFO
    elif args.verbose >= 2:
        log_level = logging.DEBUG
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s][%(name)s] %(levelname)s: %(message)s",
        force=True,
    )

    # Attempt to guess input/output file format
    if args.from_format is None:
        if args.input.lower().endswith(".html"):
            args.from_format = "html"
        elif args.input.lower().endswith(".md"):
            args.from_format = "md"
        elif os.path.isdir(args.input):
            args.from_format = "olx"
        else:
            raise LectureError("Could not detect input file format.")
        logger.info("Detected input format: %s", args.from_format)

    if args.to_format is None:
        if args.output.lower().endswith(".html"):
            args.to_format = "html"
        elif args.output.lower().endswith(".md"):
            args.to_format = "md"
        elif os.path.isdir(args.output):
            args.to_format = "olx"
        else:
            raise LectureError("Could not detect output file format.")
        logger.info("Detected output format: %s", args.to_format)

    return args


if __name__ == "__main__":
    main()
