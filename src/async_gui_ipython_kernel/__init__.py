import logging
import zmq
import sys
from enum import Enum

from typing import Any, Tuple
from tornado import gen
from ipykernel.ipkernel import IPythonKernel
from ipykernel.kernelapp import IPKernelApp
from ipykernel import kernelspec
from ipykernel.kernelspec import (
    InstallIPythonKernelSpecApp,
    make_ipkernel_cmd)

from traitlets import Unicode
from tornado.queues import Queue
import asyncio


class AsyncGUIKernel(IPythonKernel):
    implementation = 'Async GUI'
    banner = (
        'Async GUI - Allow Comm messages to be passed '
        'when other cells are running.')

    CHANNELS = dict(
        default = 0,
        kernel_info_request = 0,
        history_request = 0,
        execute_request = 0,
        comm_msg = 1)

    def _get_channels(self):
        return range(1 + max(self.CHANNELS.values()))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = self.log.getChild('AsyncGUIKernel')
        self.log.setLevel(logging.INFO)

    def start(self):
        super().start()
        self.msg_queues = [Queue() for _ in self._get_channels()]

        # a dirty hack to make `self.enter_eventloop` work with multiple queues
        setattr(self.msg_queue, 'qsize', lambda: sum(map(Queue.qsize, self.msg_queues.values())))

    def _parse_message(self, msg) -> Tuple[Any, dict]:
        """dispatch control requests"""
        idents, msg = self.session.feed_identities(msg, copy=False)
        try:
            msg = self.session.deserialize(msg, content=False, copy=False)
            return (idents, msg)
        except:
            self.log.error("Invalid Message", exc_info=True)
            return

    def schedule_dispatch(self, dispatch, *args):
        """
        Changes the schedule_dispatch dispatch method to
        always dispatch comm events.
        """

        idx = next(self._message_counter)
        msg_type = None

        if len(args) >= 1:
            indent, msg = self._parse_message(args[0])
            msg_type = msg.get('header', dict()).get('msg_type')

        channel = self.CHANNELS.get(msg_type)
        if channel is None:
            self.log.warning('unknown message type: {}'.format(msg_type))
            channel = 0
        self.msg_queues[channel].put_nowait((idx, dispatch, args))

        # ensure the eventloop wakes up
        self.io_loop.add_callback(lambda: None)


    async def _process_one_immediately(self):
        # Pick a request from any channel and exit
        msg = None
        for k in self._get_channels():
            try:
                msg = self.msg_queues[i].get_nowait()
                break
            except (asyncio.QueueEmpty, QueueEmpty):
                pass

        idx, dispatch, args = msg
        return await dispatch(*args)


    async def _fetch_request(self, channel):
        idx, dispatch, args = await self.msg_queues[channel].get()
        return dispatch(*args)


    def _fill_requests(self, channels):
        return {
            asyncio.create_task(self._fetch_request(channel)): channel
            for channel in channels}


    async def process_one(self, wait=True):
        """Process 'one' request

        While the first request is being processed it also processes requests in
        another channels.
        """
        if not wait:
            return self._process_one_immediately()

        # Here we do the following things:
        # - await on all message queues for a new request
        # - as soon as we get a request we await on it (along with the remaining message queues)
        # - as soon as we process the request we await on it's message queue again
        #
        # When we finish processing all the requests and return to awaiting on all channels again, we exit.
        # If we use single message queue we process exactly one request.
        # If we use more queues, we might process multiple requests in one go.

        channels = set(self._get_channels())
        requests = self._fill_requests(channels)
        workers = {}

        while True:
            done, pending = await asyncio.wait(
                list(requests.keys()) + list(workers.keys()),
                return_when = asyncio.FIRST_COMPLETED)

            for t in done:
                if t in requests:
                    workers[asyncio.create_task(t.result())] = requests[t]

            requests = {k: v for k, v in requests.items() if k not in done}
            workers = {k: v for k, v in workers.items() if k not in done}

            if len(workers) == 0:
                for t in requests.keys():
                    t.cancel()
                break

            requests.update(
                self._fill_requests(
                    channels - set(workers.values()) - set(requests.values())))


# Monkey patching `get_kernel_dict` to use custom `mod``

_get_kernel_dict = kernelspec.get_kernel_dict


def custom_get_kernel_dict(
        extra_arguments: list[str] | None = None,
        python_arguments: list[str] | None = None) -> dict[str, Any]:

    r = _get_kernel_dict(extra_arguments, python_arguments) | dict(
        argv = make_ipkernel_cmd(
            'async_gui_ipython_kernel',
            extra_arguments=extra_arguments,
            python_arguments=python_arguments))

    return r


kernelspec.get_kernel_dict = custom_get_kernel_dict


class InstallAsyncGUIKernelSpecApp(InstallIPythonKernelSpecApp):
    name = Unicode("async-gui-ipython-kernel-install")


class AsyncGUIKernelApp(IPKernelApp):
    name = Unicode('async-gui-ipython-kernel')

    subcommands = {
        "install": (
            "async_gui_ipython_kernel.InstallAsyncGUIKernelSpecApp",
            "Install the IPython kernel")}
