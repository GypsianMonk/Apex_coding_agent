import pytest
from core.state import ApexState, CodeFile, RequirementSpec

def test_apex_state_instantiation():
    state = ApexState(
        request="Test request",
        spec=None,
        blueprint=None,
        artifacts=[],
        tests=[],
        review=None,
        test_results=None,
        iterations=0,
        telemetry={"tokens": 0, "cost": 0.0, "latency": {}}
    )
    assert state["request"] == "Test request"
    assert len(state["artifacts"]) == 0

def test_code_file_schema():
    file = CodeFile(
        path="main.py",
        content="print('hello')",
        language="python"
    )
    assert file.path == "main.py"
    assert "hello" in file.content
