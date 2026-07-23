# -*- coding: utf-8 -*-
"""CLI 子命令测试"""
import sys
import os
import pytest
from unittest.mock import patch, MagicMock
from io import StringIO

from nexusflow.cli import (
    main, cmd_version, cmd_doctor, cmd_demo,
    _check_dependencies, _setup_logging,
)
from nexusflow import __version__


class TestCmdVersion:
    def test_version_output(self, capsys):
        args = MagicMock()
        cmd_version(args)
        captured = capsys.readouterr()
        assert __version__ in captured.out
        assert "NexusFlow" in captured.out


class TestCmdDoctor:
    def test_doctor_reports_python_version(self, capsys):
        args = MagicMock()
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test-key-12345"}):
            result = cmd_doctor(args)
        captured = capsys.readouterr()
        assert "Python" in captured.out
        assert __version__ in captured.out

    def test_doctor_detects_api_key(self, capsys):
        args = MagicMock()
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-real-key"}):
            cmd_doctor(args)
        captured = capsys.readouterr()
        assert "DEEPSEEK_API_KEY" in captured.out
        assert "✅" in captured.out

    def test_doctor_warns_missing_api_key(self, capsys):
        args = MagicMock()
        with patch.dict(os.environ, {}, clear=True):
            cmd_doctor(args)
        captured = capsys.readouterr()
        assert "未配置" in captured.out

    def test_doctor_returns_zero_when_deps_ok(self):
        args = MagicMock()
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}):
            result = cmd_doctor(args)
        assert result == 0


class TestCheckDependencies:
    def test_core_deps_present(self):
        missing = _check_dependencies()
        # numpy, requests should be installed in test env
        assert "numpy" not in missing
        assert "requests" not in missing

    def test_missing_dep_detected(self):
        with patch.dict(sys.modules, {"fastapi": None}):
            missing = _check_dependencies()
            assert "fastapi" in missing


class TestMainEntryPoint:
    def test_main_no_args_prints_help(self, capsys):
        with patch.object(sys, 'argv', ['nexusflow']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_version_command(self, capsys):
        with patch.object(sys, 'argv', ['nexusflow', 'version']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert __version__ in captured.out

    def test_main_doctor_command(self, capsys):
        with patch.object(sys, 'argv', ['nexusflow', 'doctor']):
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}):
                with pytest.raises(SystemExit) as exc_info:
                    main()
        assert exc_info.value.code == 0

    def test_main_demo_command(self, capsys):
        with patch.object(sys, 'argv', ['nexusflow', 'demo']):
            with pytest.raises(SystemExit) as exc_info:
                main()
        captured = capsys.readouterr()
        assert "Demo" in captured.out or "demo" in captured.out.lower() or exc_info.value.code == 0

    def test_main_unknown_command_exits(self):
        with patch.object(sys, 'argv', ['nexusflow', 'nonexistent']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code != 0


class TestSetupLogging:
    def test_logging_setup_no_error(self):
        _setup_logging("DEBUG")
        _setup_logging("INFO")
        _setup_logging("WARNING")

    def test_invalid_level_fallback(self):
        # Should not raise
        _setup_logging("INVALID")


class TestCmdRun:
    def test_run_without_api_key_exits(self, capsys):
        from nexusflow.cli import cmd_run
        args = MagicMock()
        args.task = "test task"
        args.log_level = "INFO"
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                cmd_run(args)
            assert exc_info.value.code == 1
