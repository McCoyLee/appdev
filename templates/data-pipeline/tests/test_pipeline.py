from src.pipeline import transform


def test_transform_shape():
    out = transform([{"a": 1}, {"a": 2}])
    assert out["count"] == 2
    assert "generated_at" in out
    assert len(out["items"]) == 2
