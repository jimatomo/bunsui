import time
import pytest

def test_pipeline_execution_performance():
    start = time.time()
    # ここでパイプライン実行処理を呼び出す（ダミー）
    time.sleep(0.1)
    elapsed = time.time() - start
    assert elapsed < 1.0 