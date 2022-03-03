class Result:
    status: bool = False
    data: dict = {}
    message: str = ""

    def __init__(
            self,
            status: bool = False,
            data: dict = None,
            message: str = ""
    ):
        if data is None:
            data = {}

        self.status = status
        self.data = data
        self.message = message
