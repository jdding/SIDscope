from setuptools import find_packages, setup


setup(
    name="sidscope-reference-adapter",
    version="0.1.0",
    description="External reference plugin for the SIDScope Adapter SDK",
    package_dir={"": "src"},
    packages=find_packages("src"),
    install_requires=["sidinspector>=1.3.0.dev0"],
    entry_points={
        "sidscope.adapters": [
            "reference-parallel=sidscope_reference_adapter:ReferenceAdapterPlugin"
        ]
    },
    python_requires=">=3.9",
)
