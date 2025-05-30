import logging


class GSettingsStub:
    @staticmethod
    def get_boolean(key: str) -> bool:
        logging.warning(f"Stub GSettings key {key}=False")
        return False
