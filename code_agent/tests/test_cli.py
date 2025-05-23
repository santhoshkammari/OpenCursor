import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from code_agent.cli import parse_args


class TestCLI(unittest.TestCase):
    """Test the command-line interface."""

    @patch("sys.argv", ["opencursor", "-q", "test query"])
    def test_default_args(self):
        """Test default arguments."""
        args = parse_args()
        self.assertEqual(args.query, "test query")
        self.assertEqual(args.workspace, os.getcwd())
        self.assertEqual(args.model, "qwen3_14b_q6k:latest")
        self.assertEqual(args.host, "http://192.168.170.76:11434")
        self.assertFalse(args.interactive)

    @patch("sys.argv", ["opencursor", "-w", "/tmp/workspace", "-q", "test query", "-i"])
    def test_custom_args(self):
        """Test custom arguments."""
        args = parse_args()
        self.assertEqual(args.query, "test query")
        self.assertEqual(args.workspace, "/tmp/workspace")
        self.assertEqual(args.model, "qwen3_14b_q6k:latest")
        self.assertTrue(args.interactive)


if __name__ == "__main__":
    unittest.main() 