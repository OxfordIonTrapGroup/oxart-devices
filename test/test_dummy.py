"""
Shows how to add unit tests that are automatically executed by the build
intrastructure. Should be deleted as soon as there are some actual unit
tests that can be used as an example.
"""

import unittest


class DummyTest(unittest.TestCase):

    def test_empty(self):
        self.assertTrue(True)
