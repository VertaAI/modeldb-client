from setuptools import setup, find_packages

with open("README.md", 'r') as f:
    long_description = f.read()

setup(
    name="verta",
    version="0.10.2",
    maintainer="Michael Liu",
    maintainer_email="miliu@verta.ai",
    description="Python client for interfacing with ModelDB and the Verta platform",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://www.verta.ai/",
    packages=find_packages(),
    python_requires=">=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*",
    install_requires=[
        "cloudpickle",
        "googleapis-common-protos>=1.5",
        "grpcio>=1.16",
        "pathlib2>=2.1",
        "pillow>=5.2, <7.0",
        "protobuf>=3.6",
        "requests>=2.21",
        "six>=1.12",
    ],
)
