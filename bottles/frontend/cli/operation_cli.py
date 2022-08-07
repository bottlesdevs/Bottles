class OperationManager:

    def __init__(self, client):
        self.client = client

    def new_task(self, task_id, title, cancellable=True):
        pass

    def update_task(self,
                    task_id,
                    count=False,
                    block_size=False,
                    total_size=False,
                    completed=False
                    ):
        pass

    def remove_task(self, task_id):
        pass

    def remove_all_tasks(self):
        pass

    def get_tasks(self):
        pass

    def get_task(self, task_id):
        pass

    def get_task_count(self):
        pass

    def get_task_ids(self):
        pass
