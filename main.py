from server import Executor, wait_for_n_executors
import time

wait_for_n_executors(3)

a = 1

with Executor():
    time.sleep(5)
    b = a + 3
    print(f"{b = }")


with Executor():
    c = b + 4
    print(f"{c = }")

with Executor():
    d = a + 5
    print(f"{d = }")
