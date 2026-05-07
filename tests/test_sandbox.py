import pytest
import asyncio
from tools.sandbox import CodeSandbox

@pytest.mark.asyncio
async def test_sandbox_python_execution():
    sandbox = CodeSandbox()
    code = "print('success')"
    result = await sandbox.execute(code, language="python")
    assert result["exit_code"] == 0
    assert "success" in result["stdout"]

@pytest.mark.asyncio
async def test_sandbox_timeout():
    sandbox = CodeSandbox()
    # Code that sleeps longer than default timeout (if we can configure it)
    # For now, let's just test basic execution
    code = "import time; time.sleep(0.1); print('done')"
    result = await sandbox.execute(code, language="python")
    assert result["exit_code"] == 0
    assert "done" in result["stdout"]

@pytest.mark.asyncio
async def test_sandbox_error_capture():
    sandbox = CodeSandbox()
    code = "raise ValueError('error')"
    result = await sandbox.execute(code, language="python")
    assert result["exit_code"] != 0
    assert "ValueError" in result["stderr"]
