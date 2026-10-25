import ontology_runtime


def test_package_imports() -> None:
    assert ontology_runtime.__version__ == "0.1.0"
