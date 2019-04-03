from setuptools import setup


with open("README.md", 'r') as f:
    long_description = f.read()

setup(
    name="verta",
    version="0.8.4",
    maintainer="Michael Liu",
    maintainer_email="miliu@verta.ai",
    description="Python client for interfacing with ModelDB",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://www.verta.ai/",
    packages=[
        "verta",
        "verta._protos.public.modeldb",
    ],
    python_requires=">= 3.5, < 3.8",
    install_requires=[
        "googleapis-common-protos~=1.5",
        "grpcio~=1.16",
        "joblib~=0.13",
        "pathlib2~=2.1",
        "protobuf~=3.6",
        "requests~=2.21",
    ],
)
