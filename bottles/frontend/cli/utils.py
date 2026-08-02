import shlex


def _quote_command_placeholder(argument: str) -> str:
    parts = argument.split("%command%")
    quoted = []
    for index, part in enumerate(parts):
        quoted.append(shlex.quote(part))
        if index < len(parts) - 1:
            quoted.extend(("'%'", "'command'", "'%'"))
    return "".join(quoted)


def serialize_arguments(arguments: list[str]) -> str:
    return " ".join(
        _quote_command_placeholder(argument)
        if "%command%" in argument
        else shlex.quote(argument)
        for argument in arguments
    )
