from multiprocessing import Manager, Pool
from sys import stdout
from time import sleep

from module_build.mock.build.root import MockBuildroot


class MockBuildPool:
    def __init__(self, workers):
        self.manager = Manager()
        self.pool = Pool(workers)
        self.currently_running = self.manager.list()  # currently running tasks in pool
        self.pool_done = False  # true when all tasks in poll are finished executing
        self.all_tasks = 0  # number of submitted taks to pool
        self.finished_tasks = 0  # number of finished tasks

    def add_job(self, *args):
        self.all_tasks += 1
        # print((*args, self.currently_running))
        self.pool.apply_async(
            MockBuildroot(*(*args, self.currently_running)).run,
            (),
            callback=self.callback,
            error_callback=self.callback,
        )
        self.update_progress()

    # This is successfoul callback
    def callback(self, result):
        print(result)
        self.currently_running.remove(result)
        self.finished_tasks += 1
        self.update_progress()

    def update_progress(self):
        sleep(0.2)  # This is here because Manager() is slow
        stdout.write("\033[K")
        print(f"Currently building ({self.finished_tasks}/{self.all_tasks}): {self.currently_running}", end="\r", flush=True)

    def wait(self):
        self.pool.close()
        self.pool.join()
