import asyncio
from queue import Queue


class HttpServerInputMessageQueue(object):
    def __init__(self, asyncio_loop):
        self.msg_queue = asyncio.Queue()
        self.asyncio_loop = asyncio_loop

    def send_message(self, **kwargs):
        """
        Send a message to the asyncio-based http server from an external thread.
        """
        coro = self.msg_queue.put(kwargs)
        asyncio.run_coroutine_threadsafe(coro, self.asyncio_loop)

    async def get_next_message(self):
        """
        Fetch the next message from the queue. Wait until a message is available.
        To be called only from the main asyncio-based thread.
        """
        return await self.msg_queue.get()


class WorkerInputQueue(object):
    def __init__(self, asyncio_loop):
        self.queue = Queue()
        self.asyncio_loop = asyncio_loop

    def add_task_with_result_future(self, task, logger):
        # logger = logger.getLogger(subsystem='worker_q')
        fut = asyncio.Future()

        async def respond_async(error, value):
            if error:
                fut.set_exception(error)
            else:
                fut.set_result(value)

        def respond(error, value):
            # logger.info('respond')
            coro = respond_async(error, value)
            asyncio.run_coroutine_threadsafe(coro, self.asyncio_loop)

        # logger.info('put in queue')
        self.queue.put((task, respond, logger))
        return fut

    def get_next_task_blocking(self):
        return self.queue.get()
