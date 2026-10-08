from setuptools import find_packages, setup


setup(
    name="sidinspector",
    version="2.0.0",
    description="Mapping-first diagnostics for semantic-ID tokenizer artifacts",
    package_dir={"": "src"},
    packages=find_packages("src"),
    install_requires=[
        "jsonschema>=4.22,<5",
        "numpy>=1.24",
        "pandas>=2.0",
        "pyarrow>=14.0",
        "scikit-learn>=1.3",
    ],
    extras_require={
        "latte": [
            "faiss-cpu>=1.8,<2",
            "sentence-transformers>=3.0,<6",
        ],
    },
    package_data={"sidinspector": ["schemas/*.json"]},
    entry_points={"console_scripts": ["sidscope=sidinspector.cli:main"]},
    python_requires=">=3.9",
)
