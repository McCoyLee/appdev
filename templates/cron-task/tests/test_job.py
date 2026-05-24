from src.job import do_job


def test_do_job_returns_non_empty_string():
    out = do_job()
    assert isinstance(out, str)
    assert len(out) > 0
