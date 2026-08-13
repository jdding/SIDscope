from setuptools import find_packages, setup


setup(
    name="sidinspector",
    version="1.0.0",
    description="Mapping-first diagnostics for semantic-ID tokenizer artifacts",
    package_dir={"": "src"},
    packages=find_packages("src"),
    install_requires=[
        "numpy>=1.24",
        "pandas>=2.0",
        "pyarrow>=14.0",
        "scikit-learn>=1.3",
    ],
    python_requires=">=3.9",
)
