import asyncio
import sys
import types
import unittest
from unittest.mock import patch

from sonic_player.input import CONTROL_C, KeyReader


class FakeContext:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeInput:
    def __init__(self):
        self.callback = None

    def raw_mode(self):
        return FakeContext()

    def attach(self, callback):
        self.callback = callback
        return FakeContext()

    def read_keys(self):
        return [
            types.SimpleNamespace(key="ordinary", data="x"),
            types.SimpleNamespace(key="control-c", data=""),
            types.SimpleNamespace(key="empty", data=""),
        ]


class InputTests(unittest.TestCase):
    def make_modules(self, fake_input):
        input_module = types.ModuleType("prompt_toolkit.input")
        input_module.create_input = lambda: fake_input
        keys_module = types.ModuleType("prompt_toolkit.keys")
        keys_module.Keys = types.SimpleNamespace(ControlC="control-c")
        package_module = types.ModuleType("prompt_toolkit")
        package_module.__path__ = []
        return {
            "prompt_toolkit": package_module,
            "prompt_toolkit.input": input_module,
            "prompt_toolkit.keys": keys_module,
        }

    def test_reader_maps_character_and_control_c_and_ignores_empty_key(self):
        fake_input = FakeInput()
        with patch.dict(sys.modules, self.make_modules(fake_input)):
            reader = KeyReader()
            with reader:
                fake_input.callback()

            async def read_two():
                return await reader.read_key(), await reader.read_key()

            self.assertEqual(asyncio.run(read_two()), ("x", CONTROL_C))

    def test_read_key_returns_empty_string_after_timeout(self):
        fake_input = FakeInput()
        with patch.dict(sys.modules, self.make_modules(fake_input)):
            reader = KeyReader()
            self.assertEqual(asyncio.run(reader.read_key(timeout=0)), "")

    def test_enter_closes_raw_mode_if_attach_fails(self):
        class BrokenInput(FakeInput):
            def attach(self, callback):
                raise RuntimeError("attach failed")

        fake_input = BrokenInput()
        with patch.dict(sys.modules, self.make_modules(fake_input)):
            reader = KeyReader()
            with self.assertRaisesRegex(RuntimeError, "attach failed"):
                reader.__enter__()


if __name__ == "__main__":
    unittest.main()
