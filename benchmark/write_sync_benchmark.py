import argparse
import time
import random
from cassandra.cluster import Cluster
from threading import Thread, Lock, Condition

MAX_NUMBER_OF_KEYS = 65536

latencies = []
finish_benchmark = False
lock_latencies = Lock()
threads_started = 0
thread_start = Condition()
benchmark_start = Condition()



def run(session) -> None:
    global latencies, real_started, threads_started

    local_latencies = []
    elapsed = None

    with thread_start:
        threads_started += 1
        thread_start.notify()

    with benchmark_start:
        benchmark_start.wait()

    while not finish_benchmark:
        key = random.randint(0, MAX_NUMBER_OF_KEYS)
        start = time.monotonic()
        session.execute("INSERT INTO test (id, value) values({}, {})".format(str(key), str(key)))
        latency = time.monotonic() - start
        local_latencies.append(latency)

    lock_latencies.acquire()
    latencies += local_latencies
    lock_latencies.release()

def benchmark(session, concurrency: int, duration: int) -> None:
    global finish_benchmark, real_started

    print("Starting threads ....")
    threads = []
    for idx in range(concurrency):
        thread = Thread(target=run, args=(session,))
        thread.start()
        threads.append(thread)

    def all_threads_started():
        return threads_started == concurrency

    # Wait till all of the threads are ready to start the benchmark
    with thread_start:
        thread_start.wait_for(all_threads_started)

    # Signal the threads to start the benchmark
    with benchmark_start:
        benchmark_start.notify_all()

    time.sleep(duration)
    finish_benchmark = True

    for thread in threads:
        thread.join()

    latencies.sort()

    total_requests = len(latencies)
    avg = sum(latencies) / total_requests 
    p90 = latencies[int((90*total_requests)/100)]
    p99 = latencies[int((99*total_requests)/100)]

    print('QPS: {0}'.format(int(total_requests/duration)))
    print('Avg: {0:.6f}'.format(avg))
    print('P90: {0:.6f}'.format(p90))
    print('P99: {0:.6f}'.format(p99))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--concurrency",
        help="Number of concurrency clients, by default 32",
        type=int,
        default=32,
    )
    parser.add_argument(
        "--duration",
        help="Test duration in seconds, by default 60",
        type=int,
        default=60,
    )
    args = parser.parse_args()

    cluster = Cluster()
    session = cluster.connect("acsylla")

    benchmark(
        session,
        args.concurrency,
        args.duration
    )