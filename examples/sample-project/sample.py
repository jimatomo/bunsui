"""Tiny sample callables for `bunsui job run`."""

import time


def main() -> None:
    print("hello from sample:main")


def async_main() -> None:
    time.sleep(0.2)
    print("hello from sample:async_main")
