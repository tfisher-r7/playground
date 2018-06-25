from playground.multiprocessing_patch import mp_posix_spawn_support

import multiprocessing
import time
import os


def add_msg_to_queue(mp_queue):
    t = 0
    print("Entering subprocess and sleeping for {} seconds".format(t))
    time.sleep(t)

    v = 42
    print("[{}] adding {} to multiprocessing.Queue".format(os.getpid(), v))
    mp_queue.put(v)


if __name__ == '__main__':
    mp_posix_spawn_support()
    multiprocessing.freeze_support()

    def main():
        ctx = multiprocessing.get_context("spawn")

        mp_queue = ctx.Queue()
        worker = ctx.Process(target=add_msg_to_queue, args=(mp_queue,))
        worker.start()

        print("[{}] created subprocess with a PID of: {}".format(os.getpid(), worker.pid))
        time.sleep(0.1)
        print("[{}] received {} from multiprocessing.Queue".format(os.getpid(), mp_queue.get()))

        worker.join()

    main()
