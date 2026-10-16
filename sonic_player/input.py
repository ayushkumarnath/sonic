"""Asynchronous single-key input using prompt_toolkit."""

import asyncio
import sys


CONTROL_C = "\x03"


class KeyReader:
    def __init__(self):
        from prompt_toolkit.input import create_input
        from prompt_toolkit.keys import Keys

        self._input = create_input()
        self._control_c_key = Keys.ControlC
        self._keys = asyncio.Queue()
        self._raw_context = None
        self._attached_context = None

    def _keys_ready(self):
        for key_press in self._input.read_keys():
            if key_press.key == self._control_c_key:
                self._keys.put_nowait(CONTROL_C)
            elif key_press.data:
                self._keys.put_nowait(key_press.data)

    def __enter__(self):
        self._raw_context = self._input.raw_mode()
        self._raw_context.__enter__()
        try:
            self._attached_context = self._input.attach(self._keys_ready)
            self._attached_context.__enter__()
        except BaseException:
            self._raw_context.__exit__(*sys.exc_info())
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self._attached_context.__exit__(exc_type, exc_value, traceback)
        finally:
            self._raw_context.__exit__(exc_type, exc_value, traceback)

    async def read_key(self, timeout=0.1):
        try:
            return await asyncio.wait_for(self._keys.get(), timeout)
        except asyncio.TimeoutError:
            return ""
