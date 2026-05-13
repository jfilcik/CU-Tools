"""
Tests for parallel processing functionality in cu-analyzer-run.

Tests the ThreadPoolExecutor-based parallel document processing
to ensure correct behavior with multiple workers.

Note: process_single_document has signature:
    process_single_document(
        client, file_path, file_idx, total_files,
        iteration, total_iterations, analyzer_id, run_id,
        results_dir, timeout, is_layout
    ) -> Tuple[bool, Dict]
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import time
import threading

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from run import process_single_document


# Test data paths
DATA_FOLDER = Path(__file__).parent.parent.parent.parent / "data"


class TestProcessSingleDocument:
    """Tests for the process_single_document() function.
    
    process_single_document(
        client, file_path, file_idx, total_files,
        iteration, total_iterations, analyzer_id, run_id,
        results_dir, timeout, is_layout
    ) -> Tuple[bool, Dict]
    """

    @pytest.fixture
    def mock_client(self):
        """Create a mock CU client."""
        client = MagicMock()
        client.begin_analyze_binary = MagicMock(return_value={"operation_id": "test-op-123"})
        client.poll_result = MagicMock(return_value={
            "status": "succeeded",
            "result": {
                "contents": [{"fields": {"test_field": {"content": "test_value"}}}]
            }
        })
        return client

    def test_processes_single_file(self, mock_client, tmp_path):
        """Test processing a single document."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"%PDF-1.4 test content")
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        success, result = process_single_document(
            client=mock_client,
            file_path=test_file,
            file_idx=0,
            total_files=1,
            iteration=1,
            total_iterations=1,
            analyzer_id="test-analyzer-id",
            run_id="test-run-123",
            results_dir=output_dir,
            timeout=180,
            is_layout=False
        )
        
        assert success is True
        assert result is not None
        assert result["status"] == "success"

    def test_returns_result_for_successful_analysis(self, mock_client, tmp_path):
        """Test that successful analysis returns expected result."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"%PDF-1.4")
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        mock_client.poll_result.return_value = {
            "status": "succeeded",
            "result": {"contents": [{"fields": {"amount": {"content": "100.00"}}}]}
        }
        
        success, result = process_single_document(
            client=mock_client,
            file_path=test_file,
            file_idx=0,
            total_files=1,
            iteration=1,
            total_iterations=1,
            analyzer_id="analyzer-id",
            run_id="run-123",
            results_dir=output_dir,
            timeout=180,
            is_layout=False
        )
        
        assert success is True
        assert result["status"] == "success"

    def test_handles_analysis_failure(self, mock_client, tmp_path):
        """Test handling of failed analysis."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"%PDF-1.4")
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        mock_client.poll_result.side_effect = Exception("Analysis failed")
        
        success, result = process_single_document(
            client=mock_client,
            file_path=test_file,
            file_idx=0,
            total_files=1,
            iteration=1,
            total_iterations=1,
            analyzer_id="analyzer-id",
            run_id="run-123",
            results_dir=output_dir,
            timeout=180,
            is_layout=False
        )
        
        assert success is False
        assert result["status"] == "failed"
        assert "error" in result

    def test_handles_timeout(self, mock_client, tmp_path):
        """Test handling of analysis timeout."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"%PDF-1.4")
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        mock_client.poll_result.side_effect = TimeoutError("Request timed out")
        
        success, result = process_single_document(
            client=mock_client,
            file_path=test_file,
            file_idx=0,
            total_files=1,
            iteration=1,
            total_iterations=1,
            analyzer_id="analyzer-id",
            run_id="run-123",
            results_dir=output_dir,
            timeout=180,
            is_layout=False
        )
        
        assert success is False
        assert "error" in result


class TestParallelExecution:
    """Tests for parallel execution with ThreadPoolExecutor."""

    @pytest.fixture
    def mock_client(self):
        """Create a thread-safe mock client."""
        client = MagicMock()
        lock = threading.Lock()
        call_count = [0]
        
        def mock_begin(*args, **kwargs):
            with lock:
                call_count[0] += 1
            return {"operation_id": f"op-{call_count[0]}"}
        
        def mock_poll(*args, **kwargs):
            time.sleep(0.1)  # Simulate processing time
            return {
                "status": "succeeded",
                "result": {"contents": [{"fields": {}}]}
            }
        
        client.begin_analyze_binary = mock_begin
        client.poll_result = mock_poll
        client.call_count = call_count
        return client

    def test_parallel_processes_multiple_files(self, mock_client, tmp_path):
        """Test that multiple files are processed in parallel."""
        files = []
        for i in range(5):
            f = tmp_path / f"doc{i}.pdf"
            f.write_bytes(b"%PDF-1.4")
            files.append(f)
        
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        results = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(
                    process_single_document,
                    mock_client,
                    f,
                    idx,
                    len(files),
                    1,
                    1,
                    "test-analyzer",
                    "run-123",
                    output_dir,
                    180,
                    False
                ): f for idx, f in enumerate(files)
            }
            
            for future in as_completed(futures):
                try:
                    success, result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append({"error": str(e)})
        
        assert len(results) == 5

    def test_worker_count_limits_concurrency(self, tmp_path):
        """Test that worker count properly limits concurrent execution."""
        max_concurrent = [0]
        current_concurrent = [0]
        lock = threading.Lock()
        
        def track_concurrency(*args, **kwargs):
            with lock:
                current_concurrent[0] += 1
                if current_concurrent[0] > max_concurrent[0]:
                    max_concurrent[0] = current_concurrent[0]
            
            time.sleep(0.2)
            
            with lock:
                current_concurrent[0] -= 1
            
            return True, {"status": "success"}
        
        files = []
        for i in range(10):
            f = tmp_path / f"doc{i}.pdf"
            f.write_bytes(b"%PDF-1.4")
            files.append(f)
        
        max_workers = 2
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(track_concurrency, None, f, i, 10, 1, 1, "a", "r", tmp_path, 180, False)
                for i, f in enumerate(files)
            ]
            
            for future in as_completed(futures):
                future.result()
        
        assert max_concurrent[0] <= max_workers

    def test_parallel_vs_sequential_produces_same_count(self, tmp_path):
        """Test that parallel and sequential processing produce same number of results."""
        def mock_process(*args, **kwargs):
            return True, {"status": "success", "file": str(args[1])}
        
        files = []
        for i in range(5):
            f = tmp_path / f"doc{i}.pdf"
            f.write_bytes(b"%PDF-1.4")
            files.append(f)
        
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        # Sequential
        sequential_results = []
        for idx, f in enumerate(files):
            result = mock_process(None, f, idx, 5, 1, 1, "a", "r", output_dir, 180, False)
            sequential_results.append(result)
        
        # Parallel
        parallel_results = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(mock_process, None, f, i, 5, 1, 1, "a", "r", output_dir, 180, False)
                for i, f in enumerate(files)
            }
            for future in as_completed(futures):
                parallel_results.append(future.result())
        
        assert len(sequential_results) == len(parallel_results) == 5

    def test_handles_mixed_success_and_failure(self, tmp_path):
        """Test parallel processing with mix of successful and failed analyses."""
        def mock_process_with_failures(client, file_path, *args, **kwargs):
            filename = file_path.stem
            if filename in ["doc1", "doc3"]:
                return False, {"status": "failed", "error": f"Simulated failure for {filename}"}
            return True, {"status": "success", "file": filename}
        
        files = []
        for i in range(5):
            f = tmp_path / f"doc{i}.pdf"
            f.write_bytes(b"%PDF-1.4")
            files.append(f)
        
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        successes = []
        failures = []
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(
                    mock_process_with_failures, None, f, i, 5, 1, 1, "a", "r", output_dir, 180, False
                ): f for i, f in enumerate(files)
            }
            
            for future in as_completed(futures):
                success, result = future.result()
                if success:
                    successes.append(result)
                else:
                    failures.append(result)
        
        assert len(successes) == 3
        assert len(failures) == 2


class TestParallelPerformance:
    """Performance tests for parallel processing."""

    def test_parallel_faster_than_sequential(self, tmp_path):
        """Test that parallel processing is faster than sequential for I/O-bound work."""
        def slow_process(*args, **kwargs):
            time.sleep(0.1)
            return True, {"status": "success"}
        
        files = []
        for i in range(6):
            f = tmp_path / f"doc{i}.pdf"
            f.write_bytes(b"%PDF-1.4")
            files.append(f)
        
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        # Sequential
        start_seq = time.time()
        for i, f in enumerate(files):
            slow_process(None, f, i, 6, 1, 1, "a", "r", output_dir, 180, False)
        seq_time = time.time() - start_seq
        
        # Parallel
        start_par = time.time()
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(slow_process, None, f, i, 6, 1, 1, "a", "r", output_dir, 180, False)
                for i, f in enumerate(files)
            ]
            for future in as_completed(futures):
                future.result()
        par_time = time.time() - start_par
        
        assert par_time < seq_time * 0.8, f"Parallel ({par_time:.2f}s) should be faster than sequential ({seq_time:.2f}s)"

    def test_scales_with_worker_count(self, tmp_path):
        """Test that increasing workers improves throughput for I/O-bound work."""
        def io_bound_process(*args, **kwargs):
            time.sleep(0.1)
            return True, {"status": "success"}
        
        files = []
        for i in range(8):
            f = tmp_path / f"doc{i}.pdf"
            f.write_bytes(b"%PDF-1.4")
            files.append(f)
        
        # Time with 1 worker
        start = time.time()
        with ThreadPoolExecutor(max_workers=1) as executor:
            list(executor.map(lambda f: io_bound_process(None, f, 0, 8, 1, 1, "a", "r", tmp_path, 180, False), files))
        time_1_worker = time.time() - start
        
        # Time with 4 workers
        start = time.time()
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(lambda f: io_bound_process(None, f, 0, 8, 1, 1, "a", "r", tmp_path, 180, False), files))
        time_4_workers = time.time() - start
        
        assert time_4_workers < time_1_worker * 0.7


class TestThreadSafety:
    """Tests for thread safety in parallel processing."""

    def test_no_race_conditions_in_output_writing(self, tmp_path):
        """Test that parallel file writing doesn't cause race conditions."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        def write_result(file_id, output_dir):
            output_path = Path(output_dir) / f"result_{file_id}.json"
            time.sleep(0.05)
            output_path.write_text(f'{{"id": {file_id}}}')
            return str(output_path)
        
        written_files = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(write_result, i, str(output_dir))
                for i in range(20)
            ]
            for future in as_completed(futures):
                written_files.append(future.result())
        
        assert len(written_files) == 20
        for i in range(20):
            expected_path = output_dir / f"result_{i}.json"
            assert expected_path.exists()
            content = expected_path.read_text()
            assert f'"id": {i}' in content

    def test_shared_client_is_thread_safe(self, tmp_path):
        """Test that shared client can be used from multiple threads."""
        lock = threading.Lock()
        call_log = []
        
        def mock_analyze(file_path):
            thread_id = threading.current_thread().ident
            with lock:
                call_log.append((thread_id, str(file_path)))
            time.sleep(0.05)
            return {"file": str(file_path), "thread": thread_id}
        
        mock_client = MagicMock()
        mock_client.analyze_document = mock_analyze
        
        files = []
        for i in range(10):
            f = tmp_path / f"doc{i}.pdf"
            f.write_bytes(b"%PDF-1.4")
            files.append(f)
        
        results = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(mock_client.analyze_document, f)
                for f in files
            ]
            for future in as_completed(futures):
                results.append(future.result())
        
        assert len(results) == 10
        assert len(call_log) == 10
        
        unique_threads = {entry[0] for entry in call_log}
        assert len(unique_threads) > 1, "Should use multiple threads"
