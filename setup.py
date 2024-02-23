from setuptools import setup, find_packages

install_requires = ["requests", "pydantic==2.*", "urllib3", "tqdm"]

setup(
    name="theia-picker",
    version="1.2.1",
    description="Theia picker",
    python_requires=">=3.8",
    author="Remi Cresson",
    author_email="remi.cresson@inrae.fr",
    license="MIT",
    zip_safe=False,
    install_requires=install_requires,
    packages=find_packages(),
    entry_points={
        'console_scripts': ['theia-picker-cli=theia_picker.cli:main', ]
    },
)

