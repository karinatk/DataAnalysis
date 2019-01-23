import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="DataAnalysis",
    version="0.0.4",
    author="Karina Tiemi Kato, Renan Santos Mendes",
    author_email="karinatkato@gmail.com",
    description="Pacote de pré-processamento de texto",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/karinatk/DataAnalysis",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)