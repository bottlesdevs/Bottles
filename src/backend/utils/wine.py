import os


class WineUtils:

    @staticmethod
    def get_user_dir(prefix_path: str):
        ignored = ["Public"]
        usersdir = os.path.join(prefix_path, "drive_c", "users")
        found = []

        for user_dir in os.listdir(usersdir):
            if user_dir in ignored:
                continue
            found.append(user_dir)

        if len(found) == 0:
            raise Exception("No user directories found.")

        return found[0]
