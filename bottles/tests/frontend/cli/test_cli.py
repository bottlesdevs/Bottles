"""Unit tests for the command-line interface."""

import shlex

from bottles.frontend.cli.utils import serialize_arguments


def test_serialize_arguments_preserves_argument_boundaries():
    assert (
        serialize_arguments(
            ["/home/user/My Documents/report.txt", "--view", "single'quote"]
        )
        == "'/home/user/My Documents/report.txt' --view 'single'\"'\"'quote'"
    )


def test_serialize_arguments_does_not_expose_steam_command_placeholder():
    arguments = [
        "/tmp/helper%command%document.txt",
        "%command%",
        "two %command% markers %command%",
    ]

    serialized = serialize_arguments(arguments)

    assert "%command%" not in serialized
    assert shlex.split(serialized) == arguments


def test_serialize_arguments_preserves_portal_document_path():
    document = "/run/user/1000/doc/abc123/My Document.txt"

    assert serialize_arguments([document]) == shlex.quote(document)
